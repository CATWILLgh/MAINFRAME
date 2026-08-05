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
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

const (
	SchemaVersion       = 2
	legacySchemaVersion = 1
	MaxRegistryBytes    = 1 << 20
	maxRawTargetBytes   = 16 << 10
)

var identifierPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`)
var digestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

type Claim struct {
	UnitID          string                 `json:"unit_id"`
	ComponentID     domain.ComponentID     `json:"component_id"`
	Target          domain.Location        `json:"target"`
	RawTarget       string                 `json:"raw_target"`
	Materialization domain.Materialization `json:"materialization,omitempty"`
	ContentSHA256   string                 `json:"content_sha256,omitempty"`
	Mode            uint32                 `json:"mode,omitempty"`
	ReleaseID       string                 `json:"release_id"`
	IndexSHA256     string                 `json:"index_sha256"`
}

type Registry struct {
	claims []Claim
}

type document struct {
	SchemaVersion int     `json:"schema_version"`
	Claims        []Claim `json:"claims"`
}

type legacyClaim struct {
	UnitID      string             `json:"unit_id"`
	ComponentID domain.ComponentID `json:"component_id"`
	Target      domain.Location    `json:"target"`
	RawTarget   string             `json:"raw_target"`
	ReleaseID   string             `json:"release_id"`
	IndexSHA256 string             `json:"index_sha256"`
}

type legacyDocument struct {
	SchemaVersion int           `json:"schema_version"`
	Claims        []legacyClaim `json:"claims"`
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
	result := append([]Claim(nil), registry.claims...)
	if result == nil {
		return []Claim{}
	}
	return result
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
	if _, err := jsondocument.Parse(payload); err != nil {
		return Registry{}, fmt.Errorf("decode ownership registry: %w", err)
	}
	var header struct {
		SchemaVersion int `json:"schema_version"`
	}
	if err := json.Unmarshal(payload, &header); err != nil {
		return Registry{}, fmt.Errorf("decode ownership registry: %w", err)
	}
	switch header.SchemaVersion {
	case legacySchemaVersion:
		return decodeLegacyRegistry(payload)
	case SchemaVersion:
		return decodeCurrentRegistry(payload)
	default:
		return Registry{}, fmt.Errorf("invalid ownership registry schema version %d", header.SchemaVersion)
	}
}

func decodeCurrentRegistry(payload []byte) (Registry, error) {
	var decoded document
	if err := decodeDocument(payload, &decoded); err != nil {
		return Registry{}, err
	}
	if decoded.Claims == nil {
		return Registry{}, fmt.Errorf("invalid ownership registry schema")
	}
	return New(decoded.Claims)
}

func decodeLegacyRegistry(payload []byte) (Registry, error) {
	var decoded legacyDocument
	if err := decodeDocument(payload, &decoded); err != nil {
		return Registry{}, err
	}
	if decoded.Claims == nil {
		return Registry{}, fmt.Errorf("invalid ownership registry schema")
	}
	claims := make([]Claim, len(decoded.Claims))
	for index, claim := range decoded.Claims {
		claims[index] = Claim{
			UnitID: claim.UnitID, ComponentID: claim.ComponentID,
			Target: claim.Target, RawTarget: claim.RawTarget,
			ReleaseID: claim.ReleaseID, IndexSHA256: claim.IndexSHA256,
		}
	}
	return New(claims)
}

func decodeDocument(payload []byte, target any) error {
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return fmt.Errorf("decode ownership registry: %w", err)
	}
	return requireEOF(decoder)
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
	if !domain.ValidUnitID(claim.UnitID) ||
		!identifierPattern.MatchString(string(claim.ComponentID)) {
		return fmt.Errorf("invalid ownership claim identity")
	}
	if !claim.Target.Valid() || !claim.Target.Path.Portable() {
		return fmt.Errorf("invalid ownership claim target")
	}
	if claim.Materialization == domain.MaterializationWritableFile {
		if claim.RawTarget != "" || !digestPattern.MatchString(claim.ContentSHA256) ||
			claim.Mode != 0o600 {
			return fmt.Errorf("invalid writable-file ownership claim")
		}
	} else {
		if claim.Materialization != "" &&
			claim.Materialization != domain.MaterializationSymlink {
			return fmt.Errorf("invalid ownership claim materialization")
		}
		if !validText(claim.RawTarget) || len(claim.RawTarget) > maxRawTargetBytes ||
			claim.ContentSHA256 != "" || claim.Mode != 0 {
			return fmt.Errorf("invalid ownership claim link target")
		}
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
