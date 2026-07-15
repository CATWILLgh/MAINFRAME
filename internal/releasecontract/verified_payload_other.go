//go:build !darwin && !linux

package releasecontract

import "fmt"

const maxJSONDocumentSize = 1 << 20

func readVerifiedPayload(_ string, _ string, _ payloadFile) ([]byte, error) {
	return nil, fmt.Errorf("verified JSON payload loading is unavailable on this platform")
}
