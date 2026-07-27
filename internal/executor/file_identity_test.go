package executor

import "testing"

func testIdentity(device, inode uint64) FileIdentity {
	return FileIdentity{
		Device:       device,
		Inode:        inode,
		BirthSeconds: int64(inode) + 1,
	}
}

func TestFileIdentityRequiresStableBirthTime(t *testing.T) {
	valid := FileIdentity{
		Device:           1,
		Inode:            2,
		BirthSeconds:     3,
		BirthNanoseconds: 4,
	}
	if !validFileIdentity(valid) {
		t.Fatal("validFileIdentity() rejected a complete identity")
	}

	tests := map[string]FileIdentity{
		"missing birth": {
			Device: 1,
			Inode:  2,
		},
		"negative nanoseconds": {
			Device:           1,
			Inode:            2,
			BirthSeconds:     3,
			BirthNanoseconds: -1,
		},
		"nanoseconds overflow": {
			Device:           1,
			Inode:            2,
			BirthSeconds:     3,
			BirthNanoseconds: 1_000_000_000,
		},
	}
	for name, identity := range tests {
		t.Run(name, func(t *testing.T) {
			if validFileIdentity(identity) {
				t.Fatal("validFileIdentity() accepted an incomplete identity")
			}
		})
	}
}

func TestFileIdentityDistinguishesReusedInodeByBirthTime(t *testing.T) {
	original := FileIdentity{
		Device:           1,
		Inode:            2,
		BirthSeconds:     3,
		BirthNanoseconds: 4,
	}
	replacement := original
	replacement.BirthNanoseconds++

	if original == replacement {
		t.Fatal("different object birth times compared equal")
	}
}
