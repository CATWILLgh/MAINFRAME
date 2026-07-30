package main

import (
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type credentialRuntimeState struct {
	definitions       credentialcatalog.Definitions
	snapshot          credentialcatalog.InstanceSnapshot
	managedReferences func() ([]mcpconfiguration.ManagedSecretReference, error)
}

func loadCredentialRuntime(
	releaseRoot string,
	release releasecontract.Release,
) (credentialRuntimeState, error) {
	definitions, err := credentialcatalog.ParseDefinitions(
		credentialcatalog.BundledDefinitionsJSON(),
		release.MCPCatalog,
	)
	if err != nil {
		return credentialRuntimeState{}, errCredentialDefinitions
	}
	layout, err := hostlayout.Resolve(hostEnvironment(), releaseRoot)
	if err != nil {
		return credentialRuntimeState{}, errCredentialLocation
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return credentialRuntimeState{}, errCredentialLocation
	}
	snapshot, err := credentialcatalog.ObserveInstances(namespace, definitions)
	if err != nil {
		return credentialRuntimeState{}, errCredentialInstancesUnsafe
	}
	return credentialRuntimeState{
		definitions: definitions,
		snapshot:    snapshot,
		managedReferences: func() (
			[]mcpconfiguration.ManagedSecretReference,
			error,
		) {
			return mcpconfiguration.ScanManagedSecretReferences(namespace)
		},
	}, nil
}
