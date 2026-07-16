//go:build darwin || linux

package linkworkspace

import "testing"

func TestParseProcessUmask(t *testing.T) {
	tests := []struct {
		name    string
		output  string
		want    uint32
		wantErr bool
	}{
		{name: "four digit octal", output: "0022\n", want: 0o022},
		{name: "three digit octal", output: "077\n", want: 0o077},
		{name: "symbolic", output: "u=rwx,g=rx,o=rx\n", wantErr: true},
		{name: "out of range", output: "1000\n", wantErr: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := parseProcessUmask([]byte(test.output))
			if (err != nil) != test.wantErr {
				t.Fatalf("parseProcessUmask() error = %v", err)
			}
			if got != test.want {
				t.Fatalf("parseProcessUmask() = %#o, want %#o", got, test.want)
			}
		})
	}
}

func TestManagedDirectoryModeCheckRejectsInvalidMode(t *testing.T) {
	workspace := Workspace{}
	for _, mode := range []uint32{0, 0o1000} {
		if err := workspace.CheckDirectoryMode(mode); err == nil {
			t.Fatalf("CheckDirectoryMode(%#o) succeeded", mode)
		}
	}
}
