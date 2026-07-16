package jsondocument

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"
	"unicode/utf8"
)

type LookupStatus string

const (
	Found        LookupStatus = "found"
	Missing      LookupStatus = "missing"
	Incompatible LookupStatus = "incompatible"
)

type Pointer struct {
	raw    string
	tokens []string
}

type Document struct {
	value any
	raw   []byte
}

func (document Document) Canonical() string {
	canonical, err := json.Marshal(document.value)
	if err != nil {
		return ""
	}
	return string(canonical)
}

func (document Document) Compact() string {
	var compact bytes.Buffer
	if err := json.Compact(&compact, document.raw); err != nil {
		return ""
	}
	return compact.String()
}

func Parse(payload []byte) (Document, error) {
	if !utf8.Valid(payload) {
		return Document{}, fmt.Errorf("JSON must be valid UTF-8")
	}
	if err := validateSurrogateEscapes(payload); err != nil {
		return Document{}, err
	}
	if err := rejectDuplicateKeys(payload); err != nil {
		return Document{}, err
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return Document{}, err
	}
	var trailing json.RawMessage
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		return Document{}, fmt.Errorf("expected one JSON value")
	}
	return Document{value: value, raw: append([]byte(nil), payload...)}, nil
}

func ParsePointer(raw string) (Pointer, error) {
	if raw == "" || raw[0] != '/' {
		return Pointer{}, fmt.Errorf("JSON pointer must be non-root and start with '/'")
	}
	encoded := strings.Split(raw[1:], "/")
	tokens := make([]string, len(encoded))
	for index, token := range encoded {
		decoded, err := decodePointerToken(token)
		if err != nil {
			return Pointer{}, fmt.Errorf("invalid JSON pointer %q: %w", raw, err)
		}
		tokens[index] = decoded
	}
	return Pointer{raw: raw, tokens: tokens}, nil
}

func (document Document) Lookup(pointer Pointer) (string, LookupStatus) {
	current := document.value
	for _, token := range pointer.tokens {
		object, valid := current.(map[string]any)
		if !valid {
			return "", Incompatible
		}
		var exists bool
		current, exists = object[token]
		if !exists {
			return "", Missing
		}
	}
	canonical, err := json.Marshal(current)
	if err != nil {
		return "", Incompatible
	}
	return string(canonical), Found
}

func (document Document) LookupOrdered(pointer Pointer) (string, LookupStatus) {
	current := json.RawMessage(document.raw)
	for _, token := range pointer.tokens {
		var object map[string]json.RawMessage
		if err := json.Unmarshal(current, &object); err != nil || object == nil {
			return "", Incompatible
		}
		var exists bool
		current, exists = object[token]
		if !exists {
			return "", Missing
		}
	}
	var compact bytes.Buffer
	if err := json.Compact(&compact, current); err != nil {
		return "", Incompatible
	}
	return compact.String(), Found
}

func Overlaps(left, right Pointer) bool {
	shorter, longer := left.tokens, right.tokens
	if len(shorter) > len(longer) {
		shorter, longer = longer, shorter
	}
	for index := range shorter {
		if shorter[index] != longer[index] {
			return false
		}
	}
	return true
}

func decodePointerToken(token string) (string, error) {
	var builder strings.Builder
	for index := 0; index < len(token); index++ {
		if token[index] != '~' {
			builder.WriteByte(token[index])
			continue
		}
		if index+1 >= len(token) || (token[index+1] != '0' && token[index+1] != '1') {
			return "", fmt.Errorf("invalid '~' escape")
		}
		index++
		if token[index] == '0' {
			builder.WriteByte('~')
		} else {
			builder.WriteByte('/')
		}
	}
	return builder.String(), nil
}

func validateSurrogateEscapes(payload []byte) error {
	insideString := false
	for index := 0; index < len(payload); index++ {
		if payload[index] == '"' {
			insideString = !insideString
			continue
		}
		if !insideString || payload[index] != '\\' {
			continue
		}
		if index+1 >= len(payload) {
			break
		}
		if payload[index+1] != 'u' {
			index++
			continue
		}
		code, valid := escapedCodeUnit(payload, index)
		if !valid {
			continue
		}
		if code >= 0xdc00 && code <= 0xdfff {
			return fmt.Errorf("JSON contains an unpaired low surrogate")
		}
		if code < 0xd800 || code > 0xdbff {
			index += 5
			continue
		}
		next := index + 6
		low, paired := escapedCodeUnit(payload, next)
		if !paired || low < 0xdc00 || low > 0xdfff {
			return fmt.Errorf("JSON contains an unpaired high surrogate")
		}
		index = next + 5
	}
	return nil
}

func escapedCodeUnit(payload []byte, slash int) (uint64, bool) {
	if slash+6 > len(payload) || payload[slash] != '\\' || payload[slash+1] != 'u' {
		return 0, false
	}
	value, err := strconv.ParseUint(string(payload[slash+2:slash+6]), 16, 16)
	return value, err == nil
}

func rejectDuplicateKeys(payload []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(payload))
	if err := scanValue(decoder); err != nil {
		return err
	}
	return nil
}

func scanValue(decoder *json.Decoder) error {
	token, err := decoder.Token()
	if err != nil {
		return err
	}
	delimiter, composite := token.(json.Delim)
	if !composite {
		return nil
	}
	if delimiter == '[' {
		return scanArray(decoder)
	}
	if delimiter != '{' {
		return fmt.Errorf("unexpected JSON delimiter %q", delimiter)
	}
	return scanObject(decoder)
}

func scanArray(decoder *json.Decoder) error {
	for decoder.More() {
		if err := scanValue(decoder); err != nil {
			return err
		}
	}
	_, err := decoder.Token()
	return err
}

func scanObject(decoder *json.Decoder) error {
	keys := make(map[string]bool)
	for decoder.More() {
		keyToken, err := decoder.Token()
		if err != nil {
			return err
		}
		key, valid := keyToken.(string)
		if !valid {
			return fmt.Errorf("JSON object key must be a string")
		}
		if keys[key] {
			return fmt.Errorf("duplicate JSON key %q", key)
		}
		keys[key] = true
		if err := scanValue(decoder); err != nil {
			return err
		}
	}
	_, err := decoder.Token()
	return err
}
