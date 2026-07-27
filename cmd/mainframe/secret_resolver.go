package main

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os/exec"
	"path/filepath"
	"regexp"
	"time"
	"unicode/utf8"
)

const secretHelperOutputLimit = 64 * 1024
const secretHelperTimeout = 10 * time.Second

var secretHelperReferencePattern = regexp.MustCompile(`^[A-Z_][A-Z0-9_]*$`)

type secretHelperResolver struct {
	path string
}

func newSecretHelperResolver(path string) secretHelperResolver {
	return secretHelperResolver{path: path}
}

func (resolver secretHelperResolver) ResolveSecret(reference string) (string, error) {
	if !filepath.IsAbs(resolver.path) {
		return "", errors.New("secret helper path is invalid")
	}
	if !secretHelperReferencePattern.MatchString(reference) {
		return "", errors.New("secret reference is invalid")
	}
	ctx, cancel := context.WithTimeout(context.Background(), secretHelperTimeout)
	defer cancel()
	command := exec.CommandContext(ctx, resolver.path, "get", reference)
	command.Stderr = io.Discard
	stdout, err := command.StdoutPipe()
	if err != nil {
		return "", errors.New("secret could not be resolved")
	}
	if err := command.Start(); err != nil {
		return "", errors.New("secret could not be resolved")
	}
	value, readErr := io.ReadAll(io.LimitReader(
		stdout,
		secretHelperOutputLimit+1,
	))
	if readErr != nil || len(value) > secretHelperOutputLimit {
		_ = command.Process.Kill()
		_ = command.Wait()
		return "", errors.New("secret helper returned an invalid value")
	}
	if err := command.Wait(); err != nil {
		return "", errors.New("secret could not be resolved")
	}
	if len(value) == 0 || bytes.IndexByte(value, 0) >= 0 ||
		!utf8.Valid(value) {
		return "", errors.New("secret helper returned an invalid value")
	}
	return string(value), nil
}
