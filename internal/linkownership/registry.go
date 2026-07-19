package linkownership

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"regexp"
	"sort"
	"unicode"
	"unicode/utf8"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

const (
	SchemaVersion     = 1
	MaxRegistryBytes  = 1 << 20
	maxRawTargetBytes = 16 << 10
)

var identifierPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`)
var digestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

type Claim struct {
	UnitID      string             `json:"unit_id"`
	ComponentID domain.ComponentID `json:"component_id"`
	Target      domain.Location    `json:"target"`
	RawTarget   string             `json:"raw_target"`
	ReleaseID   string             `json:"release_id"`
	IndexSHA256 string             `json:"index_sha256"`
}

type Registry struct {
	claims []Claim
}

type document struct {
	SchemaVersion int     `json:"schema_version"`
	Claims        []Claim `json:"claims"`
}

func New(claims []Claim) (Registry, error) {
	result := append([]Claim(nil), claims...)
	if result == nil {
		result = []Claim{}
	}
	if err := validateClaims(result); err != nil {
		return Registry{}, err
	}
	sort.Slice(result, func(left, right int) bool {
		if result[left].ComponentID != result[right].ComponentID {
			return result[left].ComponentID < result[right].ComponentID
		}
		return result[left].UnitID < result[right].UnitID
	})
	return Registry{claims: result}, nil
}

func (registry Registry) Claims() []Claim {
	return append([]Claim(nil), registry.claims...)
}

func (registry Registry) ClaimAt(target domain.Location) (Claim, bool) {
	for _, claim := range registry.claims {
		if claim.Target == target {
			return claim, true
		}
	}
	return Claim{}, false
}

func (registry Registry) Put(claim Claim) (Registry, error) {
	claims := make([]Claim, 0, len(registry.claims)+1)
	for _, current := range registry.claims {
		if current.Target != claim.Target {
			claims = append(claims, current)
		}
	}
	return New(append(claims, claim))
}

func (registry Registry) Remove(target domain.Location) (Registry, bool) {
	claims := make([]Claim, 0, len(registry.claims))
	removed := false
	for _, claim := range registry.claims {
		if claim.Target == target {
			removed = true
			continue
		}
		claims = append(claims, claim)
	}
	if !removed {
		return registry, false
	}
	return Registry{claims: claims}, true
}

func Encode(registry Registry) ([]byte, error) {
	validated, err := New(registry.claims)
	if err != nil {
		return nil, err
	}
	payload, err := json.Marshal(document{
		SchemaVersion: SchemaVersion,
		Claims:        validated.Claims(),
	})
	if err != nil {
		return nil, fmt.Errorf("encode ownership registry: %w", err)
	}
	return append(payload, '\n'), nil
}

func Decode(payload []byte) (Registry, error) {
	if len(payload) > MaxRegistryBytes {
		return Registry{}, fmt.Errorf("ownership registry exceeds %d bytes", MaxRegistryBytes)
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	var decoded document
	if err := decoder.Decode(&decoded); err != nil {
		return Registry{}, fmt.Errorf("decode ownership registry: %w", err)
	}
	if err := requireEOF(decoder); err != nil {
		return Registry{}, err
	}
	if decoded.SchemaVersion != SchemaVersion || decoded.Claims == nil {
		return Registry{}, fmt.Errorf("invalid ownership registry schema")
	}
	return New(decoded.Claims)
}

func requireEOF(decoder *json.Decoder) error {
	var trailing any
	if err := decoder.Decode(&trailing); err == io.EOF {
		return nil
	} else if err != nil {
		return fmt.Errorf("decode trailing ownership registry data: %w", err)
	}
	return fmt.Errorf("ownership registry contains trailing data")
}

func validateClaims(claims []Claim) error {
	units := make(map[string]bool, len(claims))
	targets := make(map[domain.Location]bool, len(claims))
	for _, claim := range claims {
		if err := validateClaim(claim); err != nil {
			return err
		}
		unitKey := string(claim.ComponentID) + "\x00" + claim.UnitID
		if units[unitKey] {
			return fmt.Errorf("duplicate ownership claim for %q", claim.UnitID)
		}
		if targets[claim.Target] {
			return fmt.Errorf("duplicate ownership target %#v", claim.Target)
		}
		units[unitKey] = true
		targets[claim.Target] = true
	}
	return nil
}

func validateClaim(claim Claim) error {
	if !identifierPattern.MatchString(claim.UnitID) ||
		!identifierPattern.MatchString(string(claim.ComponentID)) {
		return fmt.Errorf("invalid ownership claim identity")
	}
	if !claim.Target.Valid() || !claim.Target.Path.Portable() {
		return fmt.Errorf("invalid ownership claim target")
	}
	if !validText(claim.RawTarget) || len(claim.RawTarget) > maxRawTargetBytes {
		return fmt.Errorf("invalid ownership claim link target")
	}
	if !identifierPattern.MatchString(claim.ReleaseID) ||
		!digestPattern.MatchString(claim.IndexSHA256) {
		return fmt.Errorf("invalid ownership claim release")
	}
	return nil
}

func validText(value string) bool {
	if value == "" || !utf8.ValidString(value) {
		return false
	}
	for _, character := range value {
		if unicode.IsControl(character) {
			return false
		}
	}
	return true
}
