package secretstore

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"golang.org/x/sys/unix"
)

const (
	storeName      = "secrets.env"
	backupName     = "secrets.env.bak"
	generationName = ".generation"
	lockName       = ".lock"
)

func (store *Store) withLock(operation func() error) error {
	if err := store.ensureDirectory(); err != nil {
		return err
	}
	lock, err := openPrivateRegular(filepath.Join(store.dir, lockName), true)
	if err != nil {
		return err
	}
	defer lock.Close()
	if err := unix.Flock(int(lock.Fd()), unix.LOCK_EX); err != nil {
		return fmt.Errorf("secret store: lock unavailable")
	}
	defer unix.Flock(int(lock.Fd()), unix.LOCK_UN)
	if err := store.ensureFiles(); err != nil {
		return err
	}
	return operation()
}

func (store *Store) ensureDirectory() error {
	info, err := os.Lstat(store.dir)
	if os.IsNotExist(err) {
		if err := os.MkdirAll(filepath.Dir(store.dir), 0o700); err != nil {
			return fmt.Errorf("secret store: create parent directory")
		}
		if err := os.Mkdir(store.dir, 0o700); err != nil && !os.IsExist(err) {
			return fmt.Errorf("secret store: create directory")
		}
		info, err = os.Lstat(store.dir)
	}
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return ErrUnsafeStore
	}
	if info.Mode().Perm()&0o077 != 0 {
		if err := os.Chmod(store.dir, 0o700); err != nil {
			return ErrUnsafeStore
		}
		info, err = os.Lstat(store.dir)
		if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 ||
			info.Mode().Perm() != 0o700 {
			return ErrUnsafeStore
		}
	}
	return nil
}

func (store *Store) validateReadDirectory() error {
	info, err := os.Lstat(store.dir)
	if err != nil {
		return err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return ErrUnsafeStore
	}
	return nil
}

func (store *Store) ensureFiles() error {
	for _, name := range []string{storeName, backupName} {
		file, err := openPrivateRegular(filepath.Join(store.dir, name), true)
		if err != nil {
			return err
		}
		if err := file.Close(); err != nil {
			return fmt.Errorf("secret store: close file")
		}
	}
	generationPath := filepath.Join(store.dir, generationName)
	generation, err := openPrivateRegular(generationPath, false)
	if os.IsNotExist(err) {
		value, randomErr := randomGeneration()
		if randomErr != nil {
			return randomErr
		}
		if err := store.publish(generationName, []byte(value+"\n")); err != nil {
			return err
		}
		return nil
	}
	if err != nil {
		return err
	}
	return generation.Close()
}

func openPrivateRegular(path string, create bool) (*os.File, error) {
	flags := unix.O_CLOEXEC | unix.O_NOFOLLOW | unix.O_RDWR
	if create {
		flags |= unix.O_CREAT
	}
	return openPrivateRegularWithFlags(path, flags)
}

func openPrivateRegularReadOnly(path string) (*os.File, error) {
	return openPrivateRegularWithFlags(
		path,
		unix.O_CLOEXEC|unix.O_NOFOLLOW|unix.O_RDONLY,
	)
}

func openPrivateRegularWithFlags(path string, flags int) (*os.File, error) {
	fd, err := unix.Open(path, flags, 0o600)
	if err != nil {
		if err == unix.ELOOP {
			return nil, ErrUnsafeStore
		}
		return nil, err
	}
	file := os.NewFile(uintptr(fd), path)
	info, statErr := file.Stat()
	if statErr != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0o077 != 0 {
		file.Close()
		return nil, ErrUnsafeStore
	}
	return file, nil
}

func (store *Store) read(name string) ([]byte, error) {
	file, err := openPrivateRegularReadOnly(filepath.Join(store.dir, name))
	if err != nil {
		return nil, err
	}
	defer file.Close()
	content, err := io.ReadAll(io.LimitReader(file, maxStoreBytes+1))
	if err != nil {
		return nil, fmt.Errorf("secret store: read file")
	}
	if len(content) > maxStoreBytes {
		return nil, fmt.Errorf("%w: store is too large", ErrUnsafeStore)
	}
	return content, nil
}

func (store *Store) publish(name string, content []byte) error {
	temp, err := os.CreateTemp(store.dir, ".secret-write-*")
	if err != nil {
		return fmt.Errorf("secret store: create temporary file")
	}
	tempName := temp.Name()
	defer os.Remove(tempName)
	if err := temp.Chmod(0o600); err != nil {
		temp.Close()
		return fmt.Errorf("secret store: protect temporary file")
	}
	if _, err := temp.Write(content); err != nil {
		temp.Close()
		return fmt.Errorf("secret store: write temporary file")
	}
	if err := temp.Sync(); err != nil {
		temp.Close()
		return fmt.Errorf("secret store: synchronize temporary file")
	}
	if err := temp.Close(); err != nil {
		return fmt.Errorf("secret store: close temporary file")
	}
	if err := os.Rename(tempName, filepath.Join(store.dir, name)); err != nil {
		return fmt.Errorf("secret store: publish file")
	}
	return syncDirectory(store.dir)
}

func syncDirectory(path string) error {
	directory, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("secret store: open directory")
	}
	defer directory.Close()
	if err := directory.Sync(); err != nil {
		return fmt.Errorf("secret store: synchronize directory")
	}
	return nil
}

func randomGeneration() (string, error) {
	var value [32]byte
	if _, err := rand.Read(value[:]); err != nil {
		return "", fmt.Errorf("secret store: create generation")
	}
	return hex.EncodeToString(value[:]), nil
}
