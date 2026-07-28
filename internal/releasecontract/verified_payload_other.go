//go:build !darwin && !linux

package releasecontract

import "fmt"

const maxVerifiedPayloadSize = 1 << 20

func readVerifiedPayload(_ string, _ string, _ payloadFile) ([]byte, error) {
	return nil, fmt.Errorf("verified payload loading is unavailable on this platform")
}
