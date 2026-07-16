package jsondocument

import (
	"bytes"
	"encoding/json"
	"fmt"
)

type orderedKind uint8

const (
	orderedScalar orderedKind = iota
	orderedObject
	orderedArray
)

type orderedMember struct {
	key   string
	value orderedValue
}

type orderedValue struct {
	kind   orderedKind
	scalar any
	object []orderedMember
	array  []orderedValue
}

func (document Document) Raw() []byte {
	return append([]byte(nil), document.raw...)
}

func (document Document) Indented() []byte {
	var result bytes.Buffer
	if err := json.Indent(&result, document.raw, "", "  "); err != nil {
		return nil
	}
	result.WriteByte('\n')
	return result.Bytes()
}

func (document Document) Set(pointer Pointer, raw []byte) (Document, error) {
	replacementDocument, err := Parse(raw)
	if err != nil {
		return Document{}, fmt.Errorf("invalid replacement JSON: %w", err)
	}
	root, err := parseOrdered(document.raw)
	if err != nil {
		return Document{}, err
	}
	replacement, err := parseOrdered(replacementDocument.raw)
	if err != nil {
		return Document{}, err
	}
	if err := root.set(pointer.tokens, replacement); err != nil {
		return Document{}, err
	}
	var encoded bytes.Buffer
	if err := root.writeJSON(&encoded); err != nil {
		return Document{}, err
	}
	return Parse(encoded.Bytes())
}

func parseOrdered(raw []byte) (orderedValue, error) {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	return decodeOrdered(decoder)
}

func decodeOrdered(decoder *json.Decoder) (orderedValue, error) {
	token, err := decoder.Token()
	if err != nil {
		return orderedValue{}, err
	}
	delimiter, composite := token.(json.Delim)
	if !composite {
		return orderedValue{kind: orderedScalar, scalar: token}, nil
	}
	switch delimiter {
	case '{':
		return decodeOrderedObject(decoder)
	case '[':
		return decodeOrderedArray(decoder)
	default:
		return orderedValue{}, fmt.Errorf("unexpected JSON delimiter %q", delimiter)
	}
}

func decodeOrderedObject(decoder *json.Decoder) (orderedValue, error) {
	result := orderedValue{kind: orderedObject}
	for decoder.More() {
		key, err := decoder.Token()
		if err != nil {
			return orderedValue{}, err
		}
		value, err := decodeOrdered(decoder)
		if err != nil {
			return orderedValue{}, err
		}
		result.object = append(result.object, orderedMember{
			key: key.(string), value: value,
		})
	}
	_, err := decoder.Token()
	return result, err
}

func decodeOrderedArray(decoder *json.Decoder) (orderedValue, error) {
	result := orderedValue{kind: orderedArray}
	for decoder.More() {
		value, err := decodeOrdered(decoder)
		if err != nil {
			return orderedValue{}, err
		}
		result.array = append(result.array, value)
	}
	_, err := decoder.Token()
	return result, err
}

func (value *orderedValue) set(tokens []string, replacement orderedValue) error {
	if len(tokens) == 0 {
		return fmt.Errorf("cannot replace the document root")
	}
	if value.kind != orderedObject {
		return fmt.Errorf("JSON pointer parent is not an object")
	}
	for index := range value.object {
		if value.object[index].key != tokens[0] {
			continue
		}
		if len(tokens) == 1 {
			value.object[index].value = replacement
			return nil
		}
		return value.object[index].value.set(tokens[1:], replacement)
	}
	child := orderedValue{kind: orderedObject}
	if len(tokens) == 1 {
		child = replacement
	} else if err := child.set(tokens[1:], replacement); err != nil {
		return err
	}
	value.object = append(value.object, orderedMember{key: tokens[0], value: child})
	return nil
}

func (value orderedValue) writeJSON(output *bytes.Buffer) error {
	switch value.kind {
	case orderedScalar:
		raw, err := json.Marshal(value.scalar)
		if err != nil {
			return err
		}
		output.Write(raw)
	case orderedObject:
		return value.writeObject(output)
	case orderedArray:
		return value.writeArray(output)
	default:
		return fmt.Errorf("unknown ordered JSON value")
	}
	return nil
}

func (value orderedValue) writeObject(output *bytes.Buffer) error {
	output.WriteByte('{')
	for index, member := range value.object {
		if index > 0 {
			output.WriteByte(',')
		}
		key, err := json.Marshal(member.key)
		if err != nil {
			return err
		}
		output.Write(key)
		output.WriteByte(':')
		if err := member.value.writeJSON(output); err != nil {
			return err
		}
	}
	output.WriteByte('}')
	return nil
}

func (value orderedValue) writeArray(output *bytes.Buffer) error {
	output.WriteByte('[')
	for index, item := range value.array {
		if index > 0 {
			output.WriteByte(',')
		}
		if err := item.writeJSON(output); err != nil {
			return err
		}
	}
	output.WriteByte(']')
	return nil
}
