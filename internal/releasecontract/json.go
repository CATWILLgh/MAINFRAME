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
