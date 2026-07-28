package main

import (
	"strings"
	"testing"
)

func TestDecodeReleaseChangeAcceptsOnlyOneStrictOperationShape(t *testing.T) {
	importRequest, err := decodeReleaseChange(strings.NewReader(`{
		"schema_version":1,
		"kind":"mainframe-release-change",
		"operation":"import-and-activate",
		"source_path":"/tmp/mainframe-release"
	}`))
	if err != nil || importRequest.SourcePath != "/tmp/mainframe-release" {
		t.Fatalf("decode import request = %#v, %v", importRequest, err)
	}

	cachedRequest, err := decodeReleaseChange(strings.NewReader(`{
		"schema_version":1,
		"kind":"mainframe-release-change",
		"operation":"activate-cached",
		"release_id":"release-a",
		"index_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	}`))
	if err != nil || cachedRequest.ReleaseID != "release-a" {
		t.Fatalf("decode cached request = %#v, %v", cachedRequest, err)
	}

	rejected := []string{
		`{"schema_version":1,"kind":"mainframe-release-change","operation":"import-and-activate","source_path":"relative"}`,
		`{"schema_version":1,"kind":"mainframe-release-change","operation":"import-and-activate","source_path":"/tmp/release","release_id":"release-a"}`,
		`{"schema_version":1,"kind":"mainframe-release-change","operation":"activate-cached","release_id":"release-a"}`,
		`{"schema_version":1,"kind":"mainframe-release-change","operation":"unknown"}`,
		`{"schema_version":1,"kind":"mainframe-release-change","operation":"activate-cached","release_id":"release-a","index_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","extra":true}`,
	}
	for _, raw := range rejected {
		if _, err := decodeReleaseChange(strings.NewReader(raw)); err == nil {
			t.Fatalf("decodeReleaseChange() accepted %s", raw)
		}
	}
}

func TestDecodeReleaseApplyRequiresExactNormalizedIdentity(t *testing.T) {
	request, err := decodeReleaseApply(strings.NewReader(`{
		"schema_version":1,
		"kind":"mainframe-release-apply",
		"operation":"import-and-activate",
		"source_path":"/tmp/mainframe-release",
		"release_id":"release-a",
		"index_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	}`))
	if err != nil || request.ReleaseID != "release-a" {
		t.Fatalf("decode apply request = %#v, %v", request, err)
	}

	if _, err := decodeReleaseApply(strings.NewReader(`{
		"schema_version":1,
		"kind":"mainframe-release-apply",
		"operation":"import-and-activate",
		"source_path":"/tmp/mainframe-release",
		"release_id":"release-a",
		"index_sha256":"bad"
	}`)); err == nil {
		t.Fatal("decodeReleaseApply() accepted malformed identity")
	}
}
