package codexstate

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os/exec"
)

const (
	initializeRequestID = 0
	hooksListRequestID  = 1
	maxResponseBytes    = 4 * 1024 * 1024
)

type AppServerClient struct {
	Binary string
}

type rpcEnvelope struct {
	ID     *int            `json:"id"`
	Result json.RawMessage `json:"result"`
	Error  *rpcError       `json:"error"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type hooksListResult struct {
	Data json.RawMessage `json:"data"`
}

type hooksListRow struct {
	CWD      *string         `json:"cwd"`
	Hooks    json.RawMessage `json:"hooks"`
	Warnings json.RawMessage `json:"warnings"`
	Errors   json.RawMessage `json:"errors"`
}

type hooksListHook struct {
	SourcePath  *string      `json:"sourcePath"`
	EventName   *string      `json:"eventName"`
	HandlerType *string      `json:"handlerType"`
	Matcher     *string      `json:"matcher"`
	Command     *string      `json:"command"`
	Enabled     *bool        `json:"enabled"`
	IsManaged   *bool        `json:"isManaged"`
	TrustStatus *TrustStatus `json:"trustStatus"`
}

func NewAppServerClient() AppServerClient {
	return AppServerClient{Binary: "codex"}
}

func (client AppServerClient) ListHooks(
	ctx context.Context,
	cwd string,
) (Listing, error) {
	binary, err := exec.LookPath(client.Binary)
	if err != nil {
		if errors.Is(err, exec.ErrNotFound) {
			return Listing{}, ErrUnavailable
		}
		return Listing{}, fmt.Errorf("locate Codex: %w", err)
	}
	command := exec.CommandContext(ctx, binary, "app-server", "--stdio")
	configureCommand(command)
	stdin, err := command.StdinPipe()
	if err != nil {
		return Listing{}, fmt.Errorf("open Codex input: %w", err)
	}
	stdout, err := command.StdoutPipe()
	if err != nil {
		return Listing{}, fmt.Errorf("open Codex output: %w", err)
	}
	command.Stderr = io.Discard
	if err := command.Start(); err != nil {
		return Listing{}, fmt.Errorf("start Codex app server: %w", err)
	}
	defer reap(command, stdin)
	if err := writeRequests(stdin, cwd); err != nil {
		return Listing{}, err
	}
	return readHooksList(ctx, stdout, cwd)
}

func writeRequests(writer io.Writer, cwd string) error {
	encoder := json.NewEncoder(writer)
	requests := []any{
		map[string]any{
			"method": "initialize",
			"id":     initializeRequestID,
			"params": map[string]any{
				"clientInfo": map[string]string{
					"name":    "mainframe_installer",
					"title":   "MAINFRAME installer",
					"version": "0.1.0",
				},
			},
		},
		map[string]any{"method": "initialized", "params": map[string]any{}},
		map[string]any{
			"method": "hooks/list",
			"id":     hooksListRequestID,
			"params": map[string]any{"cwds": []string{cwd}},
		},
	}
	for _, request := range requests {
		if err := encoder.Encode(request); err != nil {
			return fmt.Errorf("write Codex request: %w", err)
		}
	}
	return nil
}

func readHooksList(
	ctx context.Context,
	reader io.ReadCloser,
	cwd string,
) (Listing, error) {
	completed := make(chan hooksListReadResult, 1)
	go func() {
		listing, err := scanHooksList(reader, cwd)
		completed <- hooksListReadResult{listing: listing, err: err}
	}()
	select {
	case result := <-completed:
		if err := ctx.Err(); err != nil {
			return Listing{}, fmt.Errorf("Codex hook inspection: %w", err)
		}
		return result.listing, result.err
	case <-ctx.Done():
		_ = reader.Close()
		<-completed
		return Listing{}, fmt.Errorf("Codex hook inspection: %w", ctx.Err())
	}
}

type hooksListReadResult struct {
	listing Listing
	err     error
}

func scanHooksList(reader io.Reader, cwd string) (Listing, error) {
	scanner := bufio.NewScanner(reader)
	scanner.Buffer(make([]byte, 4096), maxResponseBytes)
	for scanner.Scan() {
		var envelope rpcEnvelope
		if err := json.Unmarshal(scanner.Bytes(), &envelope); err != nil {
			return Listing{}, fmt.Errorf("decode Codex response: %w", err)
		}
		if envelope.ID == nil || *envelope.ID != hooksListRequestID {
			continue
		}
		return decodeHooksList(envelope, cwd)
	}
	if err := scanner.Err(); err != nil {
		return Listing{}, fmt.Errorf("read Codex response: %w", err)
	}
	return Listing{}, fmt.Errorf("Codex returned no hooks/list response")
}

func decodeHooksList(envelope rpcEnvelope, cwd string) (Listing, error) {
	if envelope.Error != nil {
		return Listing{}, fmt.Errorf(
			"Codex hooks/list error %d: %s",
			envelope.Error.Code,
			envelope.Error.Message,
		)
	}
	var result hooksListResult
	if err := json.Unmarshal(envelope.Result, &result); err != nil {
		return Listing{}, fmt.Errorf("decode Codex hooks/list result: %w", err)
	}
	var rows []hooksListRow
	if err := decodeRequiredArray(result.Data, "data", &rows); err != nil {
		return Listing{}, err
	}
	if len(rows) != 1 || rows[0].CWD == nil || *rows[0].CWD != cwd {
		return Listing{}, fmt.Errorf("Codex hooks/list returned an unexpected context")
	}
	row := rows[0]
	hooks, err := decodeHooks(row.Hooks)
	if err != nil {
		return Listing{}, err
	}
	var warnings []string
	if err := decodeRequiredArray(row.Warnings, "warnings", &warnings); err != nil {
		return Listing{}, err
	}
	var hookErrors []HookError
	if err := decodeRequiredArray(row.Errors, "errors", &hookErrors); err != nil {
		return Listing{}, err
	}
	return Listing{
		Hooks:    hooks,
		Warnings: warnings,
		Errors:   hookErrors,
	}, nil
}

func decodeHooks(raw json.RawMessage) ([]Hook, error) {
	var rows []hooksListHook
	if err := decodeRequiredArray(raw, "hooks", &rows); err != nil {
		return nil, err
	}
	hooks := make([]Hook, len(rows))
	for index, row := range rows {
		if row.SourcePath == nil ||
			row.EventName == nil ||
			row.HandlerType == nil ||
			row.Enabled == nil ||
			row.IsManaged == nil ||
			row.TrustStatus == nil {
			return nil, fmt.Errorf("Codex hooks/list returned an incomplete hook")
		}
		command := ""
		if row.Command != nil {
			command = *row.Command
		}
		hooks[index] = Hook{
			SourcePath:  *row.SourcePath,
			EventName:   *row.EventName,
			HandlerType: *row.HandlerType,
			Matcher:     row.Matcher,
			Command:     command,
			Enabled:     *row.Enabled,
			IsManaged:   *row.IsManaged,
			TrustStatus: *row.TrustStatus,
		}
	}
	return hooks, nil
}

func decodeRequiredArray(
	raw json.RawMessage,
	field string,
	target any,
) error {
	if len(raw) == 0 || bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
		return fmt.Errorf("Codex hooks/list omitted required %q field", field)
	}
	if err := json.Unmarshal(raw, target); err != nil {
		return fmt.Errorf("decode Codex hooks/list %s: %w", field, err)
	}
	return nil
}

func reap(command *exec.Cmd, stdin io.Closer) {
	_ = stdin.Close()
	_ = terminateCommand(command)
	_ = command.Wait()
}
