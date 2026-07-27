package credentialcatalog

import _ "embed"

const UserInstancesPath = "mainframe/instances.json"

//go:embed definitions.json
var bundledDefinitions []byte

func BundledDefinitionsJSON() []byte {
	return append([]byte(nil), bundledDefinitions...)
}
