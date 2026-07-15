//go:build !darwin && !linux

package hostfs

import "fmt"

func inspectNoFollow(_, _ string, _ bool) (Entry, error) {
	return Entry{}, fmt.Errorf("configuration inspection is unavailable on this platform")
}
