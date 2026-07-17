package main

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
)

func TestInspectionCacheReturnsOneImmutableSnapshotPerReadShape(t *testing.T) {
	host := &changingInspectionHost{}
	cache := newInspectionCache(host)
	location := domain.Location{
		Root: domain.RootOpenCodeConfig,
		Path: "opencode.json",
	}
	first, err := cache.Inspect(location, true)
	if err != nil {
		t.Fatal(err)
	}
	first.Content[0] = 'x'
	second, err := cache.Inspect(location, true)
	if err != nil {
		t.Fatal(err)
	}
	if host.reads != 1 || string(second.Content) != `{"version":1}` {
		t.Fatalf("reads = %d, second snapshot = %q", host.reads, second.Content)
	}
	if _, err := cache.Inspect(location, false); err != nil {
		t.Fatal(err)
	}
	if host.reads != 2 {
		t.Fatalf("read shapes were conflated: %d reads", host.reads)
	}
}

type changingInspectionHost struct {
	reads int
}

func (host *changingInspectionHost) Inspect(
	domain.Location,
	bool,
) (hostfs.Entry, error) {
	host.reads++
	return hostfs.Entry{
		Kind:    hostfs.EntryRegular,
		Content: []byte(`{"version":1}`),
	}, nil
}
