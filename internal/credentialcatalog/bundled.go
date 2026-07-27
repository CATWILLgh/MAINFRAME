package credentialcatalog

import _ "embed"

//go:embed definitions.json
var bundledDefinitions []byte

func BundledDefinitionsJSON() []byte {
	return append([]byte(nil), bundledDefinitions...)
}
