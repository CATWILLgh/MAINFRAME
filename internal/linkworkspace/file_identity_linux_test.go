//go:build linux

package linkworkspace

import (
	"strings"
	"testing"

	"golang.org/x/sys/unix"
)

func TestLinuxIdentityRequiresStatxBirthTime(t *testing.T) {
	stat := unix.Stat_t{Dev: 1, Ino: 2}
	extended := unix.Statx_t{
		Dev_major: unix.Major(1),
		Dev_minor: unix.Minor(1),
		Ino:       2,
	}

	if _, err := linuxIdentityFromStats(stat, extended); err == nil ||
		!strings.Contains(err.Error(), "birth time is unavailable") {
		t.Fatalf("linuxIdentityFromStats() error = %v", err)
	}
}

func TestLinuxIdentityDistinguishesReusedInodeByBirthTime(t *testing.T) {
	stat := unix.Stat_t{Dev: 1, Ino: 2}
	extended := unix.Statx_t{
		Mask:      unix.STATX_BTIME,
		Dev_major: unix.Major(1),
		Dev_minor: unix.Minor(1),
		Ino:       2,
		Btime:     unix.StatxTimestamp{Sec: 3, Nsec: 4},
	}
	original, err := linuxIdentityFromStats(stat, extended)
	if err != nil {
		t.Fatal(err)
	}
	extended.Btime.Nsec++
	replacement, err := linuxIdentityFromStats(stat, extended)
	if err != nil {
		t.Fatal(err)
	}
	if original == replacement {
		t.Fatal("same device and inode hid a different birth time")
	}
}
