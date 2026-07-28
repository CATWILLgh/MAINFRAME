package releasecontract

import (
	"fmt"
	"path"
)

func loadSeedContent(
	releaseRoot string,
	sourceBase string,
	source string,
	strategy ResourceStrategy,
	observation SupportStatus,
	payloadRows []payloadFile,
) ([]byte, error) {
	if strategy != StrategySeedIfAbsent ||
		observation != SupportSupported {
		return nil, nil
	}
	expected, exists := payloadRecord(payloadRows, source)
	if !exists {
		return nil, fmt.Errorf("seed source is absent from payload inventory")
	}
	content, err := readVerifiedPayload(
		releaseRoot,
		path.Join(sourceBase, source),
		expected,
	)
	if err != nil {
		return nil, err
	}
	return append([]byte{}, content...), nil
}
