package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"reflect"
	"strings"
)

func decodeStrictJSON[T any](input io.Reader) (T, error) {
	var zero T
	payload, err := io.ReadAll(io.LimitReader(input, maxPlanRequestBytes+1))
	if err != nil {
		return zero, fmt.Errorf("read request: %w", err)
	}
	if len(payload) > maxPlanRequestBytes {
		return zero, fmt.Errorf("request exceeds %d bytes", maxPlanRequestBytes)
	}
	if err := validateStrictJSONShape[T](payload); err != nil {
		return zero, err
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	var request *T
	if err := decoder.Decode(&request); err != nil {
		return zero, fmt.Errorf("decode request: %w", err)
	}
	if request == nil {
		return zero, errors.New("request must not be null")
	}
	var trailing json.RawMessage
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		return zero, errors.New("expected a single JSON request")
	}
	return *request, nil
}

func validateStrictJSONShape[T any](payload []byte) error {
	var zero T
	decoder := json.NewDecoder(bytes.NewReader(payload))
	return scanExpectedJSONValue(decoder, reflect.TypeOf(zero))
}

func scanExpectedJSONValue(
	decoder *json.Decoder,
	expected reflect.Type,
) error {
	for expected.Kind() == reflect.Pointer {
		expected = expected.Elem()
	}
	token, err := decoder.Token()
	if err != nil {
		return err
	}
	delimiter, composite := token.(json.Delim)
	if !composite {
		return nil
	}
	if expected.Kind() == reflect.Struct && delimiter == '{' {
		return scanExpectedJSONObject(decoder, expected)
	}
	if (expected.Kind() == reflect.Slice ||
		expected.Kind() == reflect.Array) &&
		delimiter == '[' {
		return scanExpectedJSONArray(decoder, expected.Elem())
	}
	return finishUntypedJSONComposite(decoder, delimiter)
}

func scanExpectedJSONObject(
	decoder *json.Decoder,
	expected reflect.Type,
) error {
	fields := jsonFieldTypes(expected)
	seen := make(map[string]bool, len(fields))
	for decoder.More() {
		keyToken, err := decoder.Token()
		if err != nil {
			return err
		}
		key, valid := keyToken.(string)
		if !valid {
			return errors.New("JSON object key must be a string")
		}
		if seen[key] {
			return errors.New("duplicate JSON key")
		}
		seen[key] = true
		fieldType, exists := fields[key]
		if !exists {
			return errors.New("request contains an unknown field")
		}
		if err := scanExpectedJSONValue(decoder, fieldType); err != nil {
			return err
		}
	}
	_, err := decoder.Token()
	return err
}

func scanExpectedJSONArray(
	decoder *json.Decoder,
	element reflect.Type,
) error {
	for decoder.More() {
		if err := scanExpectedJSONValue(decoder, element); err != nil {
			return err
		}
	}
	_, err := decoder.Token()
	return err
}

func scanUntypedJSONValue(decoder *json.Decoder) error {
	token, err := decoder.Token()
	if err != nil {
		return err
	}
	delimiter, composite := token.(json.Delim)
	if !composite {
		return nil
	}
	return finishUntypedJSONComposite(decoder, delimiter)
}

func finishUntypedJSONComposite(
	decoder *json.Decoder,
	delimiter json.Delim,
) error {
	for decoder.More() {
		if delimiter == '{' {
			if _, err := decoder.Token(); err != nil {
				return err
			}
		}
		if err := scanUntypedJSONValue(decoder); err != nil {
			return err
		}
	}
	_, err := decoder.Token()
	return err
}

func jsonFieldTypes(value reflect.Type) map[string]reflect.Type {
	result := make(map[string]reflect.Type, value.NumField())
	for index := 0; index < value.NumField(); index++ {
		field := value.Field(index)
		name := strings.Split(field.Tag.Get("json"), ",")[0]
		if name != "" && name != "-" {
			result[name] = field.Type
		}
	}
	return result
}
