//go:build darwin || linux

package releasecontract

import (
	"fmt"
	"io"
	"os"
	"strings"

	"golang.org/x/sys/unix"
)

const maxVerifiedPayloadSize = 1 << 20

func readVerifiedPayload(root, relative string, expected payloadFile) ([]byte, error) {
	if expected.Size > maxVerifiedPayloadSize {
		return nil, fmt.Errorf("verified payload %q exceeds the size limit", relative)
	}
	parent, err := unix.Open(
		root,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return nil, err
	}
	defer func() { _ = unix.Close(parent) }()
	segments := strings.Split(relative, "/")
	for _, segment := range segments[:len(segments)-1] {
		next, openErr := openPayloadDirectory(parent, segment)
		if openErr != nil {
			return nil, openErr
		}
		_ = unix.Close(parent)
		parent = next
	}
	return readPayloadFile(parent, segments[len(segments)-1], expected)
}

func openPayloadDirectory(parent int, name string) (int, error) {
	descriptor, err := unix.Openat(
		parent,
		name,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return -1, err
	}
	return descriptor, nil
}

func readPayloadFile(parent int, name string, expected payloadFile) ([]byte, error) {
	descriptor, err := unix.Openat(
		parent,
		name,
		unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return nil, err
	}
	file := os.NewFile(uintptr(descriptor), name)
	if file == nil {
		_ = unix.Close(descriptor)
		return nil, fmt.Errorf("open payload %q", name)
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() || info.Mode().Perm() != parsePayloadMode(expected.Mode) {
		return nil, fmt.Errorf("payload %q metadata mismatch", expected.Path)
	}
	content, err := io.ReadAll(io.LimitReader(file, maxVerifiedPayloadSize+1))
	if err != nil {
		return nil, err
	}
	if int64(len(content)) != expected.Size || digestBytes(content) != expected.SHA256 {
		return nil, fmt.Errorf("payload %q integrity mismatch", expected.Path)
	}
	return content, nil
}

func parsePayloadMode(value string) os.FileMode {
	var mode uint32
	_, _ = fmt.Sscanf(value, "%o", &mode)
	return os.FileMode(mode)
}
