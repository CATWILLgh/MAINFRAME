package main

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os/exec"
	"path/filepath"
	"unicode/utf8"
)

const secretHelperInputLimit = 16 * 1024

type secretHelperCreator struct {
	path string
}

func newSecretHelperCreator(path string) secretHelperCreator {
	return secretHelperCreator{path: path}
}

func (creator secretHelperCreator) CreateSecret(
	reference string,
	value []byte,
) error {
	if !filepath.IsAbs(creator.path) {
		return errors.New("secret helper path is invalid")
	}
	if !secretHelperReferencePattern.MatchString(reference) {
		return errors.New("secret reference is invalid")
	}
	if !validSecretInput(value) {
		return errors.New("secret value is invalid")
	}
	ctx, cancel := context.WithTimeout(context.Background(), secretHelperTimeout)
	defer cancel()
	command := exec.CommandContext(
		ctx,
		creator.path,
		"create-stdin",
		reference,
	)
	command.Stdin = bytes.NewReader(value)
	command.Stdout = io.Discard
	command.Stderr = io.Discard
	if err := command.Run(); err != nil {
		return errors.New("secret could not be created")
	}
	return nil
}

func validSecretInput(value []byte) bool {
	return len(value) > 0 &&
		len(value) <= secretHelperInputLimit &&
		bytes.IndexByte(value, 0) < 0 &&
		bytes.IndexAny(value, "\r\n") < 0 &&
		utf8.Valid(value)
}
