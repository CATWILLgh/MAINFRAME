package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
)

const maxPlanRequestBytes = 1 << 20

type previewLauncher func(io.Reader, io.Writer) error

type planResponse struct {
	Operations []planOperation `json:"operations"`
}

type planOperation struct {
	ComponentID domain.ComponentID   `json:"component_id"`
	Kind        domain.OperationKind `json:"kind"`
	Artifact    domain.Artifact      `json:"artifact"`
	SourcePath  domain.ArtifactPath  `json:"source_path,omitempty"`
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}

func run(args []string, input io.Reader, output, errorOutput io.Writer) int {
	return runWithPreview(args, input, output, errorOutput, runInteractivePreview)
}

func runWithPreview(
	args []string,
	input io.Reader,
	output, errorOutput io.Writer,
	launchPreview previewLauncher,
) int {
	if len(args) == 0 {
		if err := launchPreview(input, output); err != nil {
			fmt.Fprintf(errorOutput, "preview: %v\n", err)
			return 1
		}
		return 0
	}
	if len(args) != 1 || args[0] != "plan" {
		fmt.Fprintf(errorOutput, "unknown command %q; expected plan or no arguments\n", args[0])
		return 2
	}
	if err := runPlan(input, output); err != nil {
		fmt.Fprintf(errorOutput, "plan: %v\n", err)
		return 1
	}
	return 0
}

func runPlan(input io.Reader, output io.Writer) error {
	request, err := decodeRequest(input)
	if err != nil {
		return err
	}
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return err
	}
	result, err := plan.New(snapshot.release.Model.Catalog()).Plan(request)
	if err != nil {
		return err
	}
	if err := json.NewEncoder(output).Encode(publicPlanResponse(result)); err != nil {
		return fmt.Errorf("encode response: %w", err)
	}
	return nil
}

func publicPlanResponse(source domain.Plan) planResponse {
	operations := make([]planOperation, len(source.Operations))
	for index, operation := range source.Operations {
		operations[index] = planOperation{
			ComponentID: operation.ComponentID,
			Kind:        operation.Kind,
			Artifact:    operation.Artifact,
			SourcePath:  operation.SourcePath,
		}
	}
	return planResponse{Operations: operations}
}

func decodeRequest(input io.Reader) (domain.PlanRequest, error) {
	payload, err := io.ReadAll(io.LimitReader(input, maxPlanRequestBytes+1))
	if err != nil {
		return domain.PlanRequest{}, fmt.Errorf("read request: %w", err)
	}
	if len(payload) > maxPlanRequestBytes {
		return domain.PlanRequest{}, fmt.Errorf("request exceeds %d bytes", maxPlanRequestBytes)
	}
	if err := rejectDuplicateJSONKeys(payload); err != nil {
		return domain.PlanRequest{}, err
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	var request *domain.PlanRequest
	if err := decoder.Decode(&request); err != nil {
		return domain.PlanRequest{}, fmt.Errorf("decode request: %w", err)
	}
	if request == nil {
		return domain.PlanRequest{}, fmt.Errorf("request must not be null")
	}
	var trailing json.RawMessage
	err = decoder.Decode(&trailing)
	if !errors.Is(err, io.EOF) {
		return domain.PlanRequest{}, fmt.Errorf("expected a single JSON request")
	}
	return *request, nil
}

func rejectDuplicateJSONKeys(payload []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(payload))
	if err := scanJSONValue(decoder); err != nil {
		return fmt.Errorf("decode request: %w", err)
	}
	return nil
}

func scanJSONValue(decoder *json.Decoder) error {
	token, err := decoder.Token()
	if err != nil {
		return err
	}
	delimiter, composite := token.(json.Delim)
	if !composite {
		return nil
	}
	if delimiter == '[' {
		for decoder.More() {
			if err := scanJSONValue(decoder); err != nil {
				return err
			}
		}
		_, err = decoder.Token()
		return err
	}
	if delimiter != '{' {
		return fmt.Errorf("unexpected JSON delimiter %q", delimiter)
	}
	keys := make(map[string]bool)
	for decoder.More() {
		keyToken, err := decoder.Token()
		if err != nil {
			return err
		}
		key, valid := keyToken.(string)
		if !valid {
			return fmt.Errorf("JSON object key must be a string")
		}
		if keys[key] {
			return fmt.Errorf("duplicate JSON key %q", key)
		}
		keys[key] = true
		if err := scanJSONValue(decoder); err != nil {
			return err
		}
	}
	_, err = decoder.Token()
	return err
}
