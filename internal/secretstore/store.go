package secretstore

import (
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

var (
	ErrNotFound          = errors.New("secret entry not found")
	ErrAlreadyExists     = errors.New("secret entry already exists")
	ErrGenerationChanged = errors.New("secret store generation changed")
	ErrInvalidInput      = errors.New("invalid secret input")
	ErrUnsafeStore       = errors.New("credential store is unsafe")
)

type FailurePoint string

const (
	BeforeGenerationPublication FailurePoint = "before-generation-publication"
	BeforeBackupPublication     FailurePoint = "before-backup-publication"
	BeforePrimaryPublication    FailurePoint = "before-primary-publication"
)

type Store struct {
	dir     string
	failure func(FailurePoint) error
	editor  func(string) error
}

func New(directory string) *Store {
	return &Store{dir: directory}
}

func (store *Store) Path() string {
	return filepath.Join(store.dir, storeName)
}

func (store *Store) BackupPath() string {
	return filepath.Join(store.dir, backupName)
}

func (store *Store) Set(name, value string) error {
	if err := validateName(name); err != nil {
		return err
	}
	if err := validateValue(value); err != nil {
		return err
	}
	return store.mutate(func(entries map[string]string) error {
		entries[name] = value
		return nil
	})
}

func (store *Store) Create(name string, input io.Reader) error {
	if err := validateName(name); err != nil {
		return err
	}
	value, err := readValue(input)
	if err != nil {
		return err
	}
	return store.mutate(func(entries map[string]string) error {
		if _, exists := entries[name]; exists {
			return ErrAlreadyExists
		}
		entries[name] = value
		return nil
	})
}

func (store *Store) Get(name string) (string, error) {
	if err := validateName(name); err != nil {
		return "", err
	}
	if err := store.validateReadDirectory(); err != nil {
		if os.IsNotExist(err) {
			return "", ErrNotFound
		}
		return "", err
	}
	document, err := store.load()
	if err != nil {
		if os.IsNotExist(err) {
			return "", ErrNotFound
		}
		return "", err
	}
	value, exists := document.entries[name]
	if !exists {
		return "", ErrNotFound
	}
	return value, nil
}

func (store *Store) List() ([]string, error) {
	var names []string
	if err := store.validateReadDirectory(); err != nil {
		if os.IsNotExist(err) {
			return names, nil
		}
		return nil, err
	}
	document, err := store.load()
	if err != nil {
		if os.IsNotExist(err) {
			return names, nil
		}
		return nil, err
	}
	for name := range document.entries {
		names = append(names, name)
	}
	sortStrings(names)
	return names, nil
}

func (store *Store) Delete(name string) error {
	if err := validateName(name); err != nil {
		return err
	}
	return store.mutate(func(entries map[string]string) error {
		delete(entries, name)
		return nil
	})
}

func (store *Store) PrepareRetire(name string) (string, error) {
	if err := validateName(name); err != nil {
		return "", err
	}
	var generation string
	err := store.withLock(func() error {
		document, err := store.load()
		if err != nil {
			return err
		}
		if _, exists := document.entries[name]; !exists {
			return ErrNotFound
		}
		generation, err = store.readGeneration()
		return err
	})
	return generation, err
}

func (store *Store) DeleteIfGeneration(name, expected string) error {
	if err := validateName(name); err != nil || expected == "" {
		if err != nil {
			return err
		}
		return ErrInvalidInput
	}
	return store.mutateChecked(expected, func(entries map[string]string) error {
		if _, exists := entries[name]; !exists {
			return ErrNotFound
		}
		delete(entries, name)
		return nil
	})
}

func (store *Store) Edit() error {
	return store.withLock(func() error {
		document, err := store.load()
		if err != nil {
			return err
		}
		temp, err := store.editTemporary(encode(document))
		if err != nil {
			return err
		}
		defer os.Remove(temp)
		editedFile, err := openPrivateRegularReadOnly(temp)
		if err != nil {
			return err
		}
		content, err := io.ReadAll(io.LimitReader(editedFile, maxStoreBytes+1))
		closeErr := editedFile.Close()
		if err != nil {
			return fmt.Errorf("secret store: read edited file")
		}
		if closeErr != nil {
			return fmt.Errorf("secret store: close edited file")
		}
		if len(content) > maxStoreBytes {
			return fmt.Errorf("%w: edited store is too large", ErrInvalidInput)
		}
		edited, err := parse(content)
		if err != nil {
			return err
		}
		return store.commit(edited)
	})
}

func (store *Store) mutate(change func(map[string]string) error) error {
	return store.withLock(func() error {
		document, err := store.load()
		if err != nil {
			return err
		}
		if err := change(document.entries); err != nil {
			return err
		}
		return store.commit(document)
	})
}

func (store *Store) mutateChecked(expected string, change func(map[string]string) error) error {
	return store.withLock(func() error {
		generation, err := store.readGeneration()
		if err != nil {
			return err
		}
		if generation != expected {
			return ErrGenerationChanged
		}
		document, err := store.load()
		if err != nil {
			return err
		}
		if err := change(document.entries); err != nil {
			return err
		}
		return store.commit(document)
	})
}

func (store *Store) commit(document document) error {
	content := encode(document)
	if len(content) > maxStoreBytes {
		return ErrInvalidInput
	}
	generation, err := randomGeneration()
	if err != nil {
		return err
	}
	if err := store.inject(BeforeGenerationPublication); err != nil {
		return err
	}
	if err := store.publish(generationName, []byte(generation+"\n")); err != nil {
		return err
	}
	if err := store.inject(BeforeBackupPublication); err != nil {
		return err
	}
	if err := store.publish(backupName, content); err != nil {
		return err
	}
	if err := store.inject(BeforePrimaryPublication); err != nil {
		return err
	}
	return store.publish(storeName, content)
}

func (store *Store) load() (document, error) {
	content, err := store.read(storeName)
	if err != nil {
		return document{}, err
	}
	return parse(content)
}

func (store *Store) readGeneration() (string, error) {
	content, err := store.read(generationName)
	if err != nil {
		return "", err
	}
	value := strings.TrimSuffix(string(content), "\n")
	if len(value) != 64 {
		return "", ErrUnsafeStore
	}
	if _, err := hex.DecodeString(value); err != nil {
		return "", ErrUnsafeStore
	}
	return value, nil
}

func (store *Store) editTemporary(content []byte) (string, error) {
	temp, err := os.CreateTemp(store.dir, ".secret-edit-*")
	if err != nil {
		return "", fmt.Errorf("secret store: create edit file")
	}
	path := temp.Name()
	if err := temp.Chmod(0o600); err == nil {
		_, err = temp.Write(content)
	}
	if closeErr := temp.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		os.Remove(path)
		return "", fmt.Errorf("secret store: prepare edit file")
	}
	editor := store.editor
	if editor == nil {
		editor = runEditor
	}
	if err := editor(path); err != nil {
		os.Remove(path)
		return "", fmt.Errorf("secret store: editor failed")
	}
	return path, nil
}

func runEditor(path string) error {
	editor := os.Getenv("EDITOR")
	if editor == "" {
		editor = os.Getenv("VISUAL")
	}
	if editor == "" {
		editor = "vi"
	}
	command := exec.Command(editor, path)
	command.Stdin, command.Stdout, command.Stderr = os.Stdin, os.Stdout, os.Stderr
	return command.Run()
}

func readValue(input io.Reader) (string, error) {
	content, err := io.ReadAll(io.LimitReader(input, maxValueBytes+1))
	if err != nil || len(content) > maxValueBytes {
		return "", ErrInvalidInput
	}
	value := string(content)
	if err := validateValue(value); err != nil {
		return "", err
	}
	return value, nil
}

func (store *Store) inject(point FailurePoint) error {
	if store.failure == nil {
		return nil
	}
	if err := store.failure(point); err != nil {
		return fmt.Errorf("secret store: publication interrupted")
	}
	return nil
}

func sortStrings(values []string) {
	for index := 1; index < len(values); index++ {
		for cursor := index; cursor > 0 && values[cursor] < values[cursor-1]; cursor-- {
			values[cursor], values[cursor-1] = values[cursor-1], values[cursor]
		}
	}
}
