package codexstate

import (
	"context"
	"errors"
)

var ErrUnavailable = errors.New("Codex hook state is unavailable")

type TrustStatus string

const (
	TrustManaged   TrustStatus = "managed"
	TrustUntrusted TrustStatus = "untrusted"
	TrustTrusted   TrustStatus = "trusted"
	TrustModified  TrustStatus = "modified"
)

type Hook struct {
	SourcePath  string      `json:"sourcePath"`
	EventName   string      `json:"eventName"`
	HandlerType string      `json:"handlerType"`
	Matcher     *string     `json:"matcher"`
	Command     string      `json:"command"`
	Enabled     bool        `json:"enabled"`
	IsManaged   bool        `json:"isManaged"`
	TrustStatus TrustStatus `json:"trustStatus"`
}

type Listing struct {
	Hooks    []Hook
	Warnings []string
	Errors   []HookError
}

type HookError struct {
	Path    string `json:"path"`
	Message string `json:"message"`
}

type Client interface {
	ListHooks(context.Context, string) (Listing, error)
}
