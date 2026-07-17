package main

import (
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
)

type inspectionReader interface {
	Inspect(domain.Location, bool) (hostfs.Entry, error)
}

type inspectionCacheKey struct {
	location       domain.Location
	includeContent bool
}

type inspectionCacheValue struct {
	entry hostfs.Entry
	err   error
}

type inspectionCache struct {
	host    inspectionReader
	entries map[inspectionCacheKey]inspectionCacheValue
}

func newInspectionCache(host inspectionReader) *inspectionCache {
	return &inspectionCache{
		host:    host,
		entries: make(map[inspectionCacheKey]inspectionCacheValue),
	}
}

func (cache *inspectionCache) Inspect(
	location domain.Location,
	includeContent bool,
) (hostfs.Entry, error) {
	key := inspectionCacheKey{location: location, includeContent: includeContent}
	value, exists := cache.entries[key]
	if !exists {
		entry, err := cache.host.Inspect(location, includeContent)
		value = inspectionCacheValue{entry: cloneInspectionEntry(entry), err: err}
		cache.entries[key] = value
	}
	return cloneInspectionEntry(value.entry), value.err
}

func cloneInspectionEntry(entry hostfs.Entry) hostfs.Entry {
	entry.Content = append([]byte(nil), entry.Content...)
	return entry
}
