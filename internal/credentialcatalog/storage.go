package credentialcatalog

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io/fs"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
)

const credentialDocumentMode uint32 = 0o600
const credentialResourceID = "credentials.instances"

var userInstancesLocation = domain.Location{
	Root: domain.RootCredentialsConfig,
	Path: UserInstancesPath,
}

type InstanceHost interface {
	Inspect(domain.Location, bool) (hostfs.Entry, error)
}

type InstanceSnapshot struct {
	definitions Definitions
	instances   Instances
	content     []byte
	entry       hostfs.Entry
	present     bool
}

func ObserveInstances(
	host InstanceHost,
	definitions Definitions,
) (InstanceSnapshot, error) {
	if host == nil {
		return InstanceSnapshot{}, fmt.Errorf("credential instance host must not be nil")
	}
	entry, err := host.Inspect(userInstancesLocation, true)
	if errors.Is(err, fs.ErrNotExist) {
		empty, buildErr := BuildInstances(nil, definitions)
		if buildErr != nil {
			return InstanceSnapshot{}, buildErr
		}
		return InstanceSnapshot{
			definitions: definitions,
			instances:   empty,
		}, nil
	}
	if err != nil {
		return InstanceSnapshot{}, fmt.Errorf("inspect credential instances: %w", err)
	}
	if entry.Kind != hostfs.EntryRegular || entry.Mode != credentialDocumentMode {
		return InstanceSnapshot{}, fmt.Errorf("credential instance document is unsafe")
	}
	instances, err := ParseInstances(entry.Content, definitions)
	if err != nil {
		return InstanceSnapshot{}, fmt.Errorf("parse credential instances: %w", err)
	}
	return InstanceSnapshot{
		definitions: definitions,
		instances:   instances,
		content:     append([]byte(nil), entry.Content...),
		entry:       entry,
		present:     true,
	}, nil
}

func (snapshot InstanceSnapshot) Instances() Instances {
	return Instances{instances: snapshot.instances.All()}
}

func (snapshot InstanceSnapshot) Prepare(
	desired Instances,
) (configuration.PreparedPlan, error) {
	payload, err := EncodeInstances(desired)
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	if _, err := ParseInstances(payload, snapshot.definitions); err != nil {
		return configuration.PreparedPlan{}, fmt.Errorf(
			"validate prepared credential instances: %w",
			err,
		)
	}
	if snapshot.present && reflect.DeepEqual(
		snapshot.instances.All(),
		desired.All(),
	) {
		return configuration.PreparedPlan{}, nil
	}
	mutation := configuration.FileMutation{
		Disposition: configuration.MutationPresent,
		Target:      userInstancesLocation,
		Before:      snapshot.beforeImage(),
		After: configuration.AfterImage{
			Exists:  true,
			Content: payload,
			Mode:    credentialDocumentMode,
		},
	}
	return configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs: []string{credentialResourceID},
		Mutations:   []configuration.FileMutation{mutation},
	}})
}

func IsInstancesOnlyPlan(plan configuration.PreparedPlan) bool {
	transitions := plan.Transitions()
	if len(transitions) != 1 ||
		len(plan.Preconditions()) != 0 ||
		len(transitions[0].ResourceIDs) != 1 ||
		transitions[0].ResourceIDs[0] != credentialResourceID ||
		len(transitions[0].Mutations) != 1 {
		return false
	}
	mutation := transitions[0].Mutations[0]
	return mutation.Target == userInstancesLocation &&
		mutation.Disposition == configuration.MutationPresent &&
		mutation.After.Exists &&
		mutation.After.Mode == credentialDocumentMode &&
		len(mutation.After.Content) > 0
}

func ValidateInstancesOnlyPlan(
	plan configuration.PreparedPlan,
	desired Instances,
) error {
	if !IsInstancesOnlyPlan(plan) {
		return fmt.Errorf("configuration plan is not credential-only")
	}
	payload, err := EncodeInstances(desired)
	if err != nil {
		return err
	}
	mutation := plan.Transitions()[0].Mutations[0]
	if !bytes.Equal(mutation.After.Content, payload) {
		return fmt.Errorf("credential after-image differs from reviewed state")
	}
	return nil
}

func (snapshot InstanceSnapshot) beforeImage() configuration.BeforeImage {
	if !snapshot.present {
		return configuration.BeforeImage{}
	}
	digest := sha256.Sum256(snapshot.content)
	return configuration.BeforeImage{
		Exists:           true,
		SHA256:           hex.EncodeToString(digest[:]),
		Mode:             snapshot.entry.Mode,
		Device:           snapshot.entry.Device,
		Inode:            snapshot.entry.Inode,
		BirthSeconds:     snapshot.entry.BirthSeconds,
		BirthNanoseconds: snapshot.entry.BirthNanoseconds,
	}
}
