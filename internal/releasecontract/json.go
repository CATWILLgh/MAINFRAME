package releasecontract

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

func decodeStrict(payload []byte, target any) error {
	if _, err := jsondocument.Parse(payload); err != nil {
		return err
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	var trailing json.RawMessage
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		return fmt.Errorf("expected one JSON value")
	}
	return nil
}

func (list *optionalStringList) UnmarshalJSON(payload []byte) error {
	list.Present = true
	if bytes.Equal(bytes.TrimSpace(payload), []byte("null")) {
		return fmt.Errorf("string list must not be null")
	}
	return json.Unmarshal(payload, &list.Values)
}

func (ownership *optionalJSONMapOwnership) UnmarshalJSON(payload []byte) error {
	ownership.Present = true
	if bytes.Equal(bytes.TrimSpace(payload), []byte("null")) {
		return fmt.Errorf("JSON map ownership must not be null")
	}
	return decodeStrict(payload, &ownership.Value)
}

func (ownership *optionalFileOwnership) UnmarshalJSON(payload []byte) error {
	ownership.Present = true
	if bytes.Equal(bytes.TrimSpace(payload), []byte("null")) {
		return fmt.Errorf("file ownership must not be null")
	}
	return decodeStrict(payload, &ownership.Value)
}

func (ownership *optionalJSONClaimOwnership) UnmarshalJSON(payload []byte) error {
	ownership.Present = true
	if bytes.Equal(bytes.TrimSpace(payload), []byte("null")) {
		return fmt.Errorf("JSON claim ownership must not be null")
	}
	return decodeStrict(payload, &ownership.Value)
}

func (externalState *optionalExternalState) UnmarshalJSON(payload []byte) error {
	externalState.Present = true
	if bytes.Equal(bytes.TrimSpace(payload), []byte("null")) {
		return fmt.Errorf("external state must not be null")
	}
	return decodeStrict(payload, &externalState.Value)
}

func (requirements *optionalHostRequirements) UnmarshalJSON(payload []byte) error {
	requirements.Present = true
	if bytes.Equal(bytes.TrimSpace(payload), []byte("null")) {
		return fmt.Errorf("host requirements must not be null")
	}
	return decodeStrict(payload, &requirements.Values)
}

func (feature *optionalFeature) UnmarshalJSON(payload []byte) error {
	feature.Present = true
	if bytes.Equal(bytes.TrimSpace(payload), []byte("null")) {
		return fmt.Errorf("feature must not be null")
	}
	return json.Unmarshal(payload, &feature.Value)
}

func (materialization *optionalMaterialization) UnmarshalJSON(payload []byte) error {
	materialization.Present = true
	if bytes.Equal(bytes.TrimSpace(payload), []byte("null")) {
		return fmt.Errorf("materialization must not be null")
	}
	return json.Unmarshal(payload, &materialization.Value)
}
