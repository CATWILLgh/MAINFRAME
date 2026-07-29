package credentialmigration

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
)

type legacySourceEvidence struct {
	Captured         bool
	Location         domain.Location
	State            IndexState
	SHA256           string
	Mode             uint32
	Device           uint64
	Inode            uint64
	BirthSeconds     int64
	BirthNanoseconds int64
}

type legacySourceCommitmentEnvelope struct {
	SchemaVersion int                                `json:"schema_version"`
	Kind          string                             `json:"kind"`
	ReleaseID     string                             `json:"release_id"`
	Sources       []legacySourceCommitmentDescriptor `json:"sources"`
}

type legacySourceCommitmentDescriptor struct {
	ComponentID      domain.ComponentID  `json:"component_id"`
	ResourceID       string              `json:"resource_id"`
	SourceRole       SourceRole          `json:"source_role"`
	Root             domain.RootID       `json:"root"`
	Path             domain.ArtifactPath `json:"path"`
	State            IndexState          `json:"state"`
	SHA256           string              `json:"sha256,omitempty"`
	Mode             uint32              `json:"mode,omitempty"`
	Device           uint64              `json:"device,omitempty"`
	Inode            uint64              `json:"inode,omitempty"`
	BirthSeconds     int64               `json:"birth_seconds,omitempty"`
	BirthNanoseconds int64               `json:"birth_nanoseconds,omitempty"`
}

func LegacyTransferSourceCommitment(
	plan LegacyTransferPlan,
) (string, error) {
	if plan.ReleaseID == "" || len(plan.Sources) == 0 {
		return "", fmt.Errorf("legacy transfer plan has no source evidence")
	}
	sources := make(
		[]legacySourceCommitmentDescriptor,
		len(plan.Sources),
	)
	for index, source := range plan.Sources {
		if !source.evidence.Captured {
			return "", fmt.Errorf(
				"legacy transfer source evidence is incomplete",
			)
		}
		sources[index] = publicLegacySourceCommitment(source)
	}
	payload, err := json.Marshal(legacySourceCommitmentEnvelope{
		SchemaVersion: 1,
		Kind:          "mainframe-legacy-credential-source-commitment",
		ReleaseID:     plan.ReleaseID,
		Sources:       sources,
	})
	if err != nil {
		return "", fmt.Errorf("encode legacy source commitment: %w", err)
	}
	digest := sha256.Sum256(payload)
	return "sha256:" + hex.EncodeToString(digest[:]), nil
}

func publicLegacySourceCommitment(
	source LegacyPlanSource,
) legacySourceCommitmentDescriptor {
	evidence := source.evidence
	return legacySourceCommitmentDescriptor{
		ComponentID:      source.ComponentID,
		ResourceID:       source.ResourceID,
		SourceRole:       source.SourceRole,
		Root:             evidence.Location.Root,
		Path:             evidence.Location.Path,
		State:            evidence.State,
		SHA256:           evidence.SHA256,
		Mode:             evidence.Mode,
		Device:           evidence.Device,
		Inode:            evidence.Inode,
		BirthSeconds:     evidence.BirthSeconds,
		BirthNanoseconds: evidence.BirthNanoseconds,
	}
}

func missingLegacySourceEvidence(
	location domain.Location,
) legacySourceEvidence {
	return legacySourceEvidence{
		Captured: true,
		Location: location,
		State:    IndexMissing,
	}
}

func unsafeLegacySourceEvidence(
	location domain.Location,
) legacySourceEvidence {
	return legacySourceEvidence{
		Captured: true,
		Location: location,
		State:    IndexUnsafe,
	}
}

func legacySourceEvidenceFromEntry(
	location domain.Location,
	state IndexState,
	entry hostfs.Entry,
) legacySourceEvidence {
	digest := sha256.Sum256(entry.Content)
	return legacySourceEvidence{
		Captured:         true,
		Location:         location,
		State:            state,
		SHA256:           hex.EncodeToString(digest[:]),
		Mode:             entry.Mode,
		Device:           entry.Device,
		Inode:            entry.Inode,
		BirthSeconds:     entry.BirthSeconds,
		BirthNanoseconds: entry.BirthNanoseconds,
	}
}
