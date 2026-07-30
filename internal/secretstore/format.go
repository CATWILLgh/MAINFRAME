package secretstore

import (
	"fmt"
	"sort"
	"strings"
)

const (
	maxValueBytes = 16 * 1024
	maxStoreBytes = 1 << 20
)

type document struct {
	entries  map[string]string
	preamble []string
}

func validateName(name string) error {
	if name == "" {
		return fmt.Errorf("%w: empty name", ErrInvalidInput)
	}
	for index, character := range name {
		valid := character == '_' ||
			character >= 'A' && character <= 'Z' ||
			index > 0 && character >= '0' && character <= '9'
		if !valid {
			return fmt.Errorf("%w: name must match [A-Z_][A-Z0-9_]*", ErrInvalidInput)
		}
	}
	return nil
}

func validateValue(value string) error {
	if value == "" || len(value) > maxValueBytes ||
		strings.ContainsAny(value, "\x00\n\r") {
		return fmt.Errorf("%w: value is invalid", ErrInvalidInput)
	}
	return nil
}

func parse(content []byte) (document, error) {
	result := document{entries: make(map[string]string)}
	if len(content) > maxStoreBytes {
		return document{}, fmt.Errorf("%w: store is too large", ErrUnsafeStore)
	}
	lines := strings.Split(string(content), "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			result.preamble = append(result.preamble, line)
			continue
		}
		separator := strings.IndexByte(line, '=')
		if separator < 1 {
			return document{}, fmt.Errorf("%w: malformed store", ErrUnsafeStore)
		}
		name, encoded := line[:separator], line[separator+1:]
		if err := validateName(name); err != nil {
			return document{}, fmt.Errorf("%w: malformed store", ErrUnsafeStore)
		}
		value, err := decodeValue(encoded)
		if err != nil {
			return document{}, err
		}
		if _, duplicate := result.entries[name]; duplicate {
			return document{}, fmt.Errorf("%w: duplicate entry", ErrUnsafeStore)
		}
		result.entries[name] = value
	}
	return result, nil
}

func decodeValue(encoded string) (string, error) {
	if len(encoded) >= 2 &&
		encoded[0] == '\'' &&
		encoded[len(encoded)-1] == '\'' {
		value := strings.ReplaceAll(encoded[1:len(encoded)-1], "'\\''", "'")
		if encodeValue(value) != encoded {
			return "", fmt.Errorf("%w: malformed quoted value", ErrUnsafeStore)
		}
		return validatedStoredValue(value)
	}
	if len(encoded) >= 2 &&
		encoded[0] == '"' &&
		encoded[len(encoded)-1] == '"' {
		value := encoded[1 : len(encoded)-1]
		if strings.ContainsAny(value, "\\$`\"") {
			return "", fmt.Errorf("%w: unsafe double-quoted value", ErrUnsafeStore)
		}
		return validatedStoredValue(value)
	}
	if encoded == "" || strings.ContainsAny(encoded, " \t\\'\"$`;&|<>(){}[]*?!#") {
		return "", fmt.Errorf("%w: unsafe unquoted value", ErrUnsafeStore)
	}
	return validatedStoredValue(encoded)
}

func validatedStoredValue(value string) (string, error) {
	if err := validateValue(value); err != nil {
		return "", fmt.Errorf("%w: malformed value", ErrUnsafeStore)
	}
	return value, nil
}

func encode(source document) []byte {
	names := make([]string, 0, len(source.entries))
	for name := range source.entries {
		names = append(names, name)
	}
	sort.Strings(names)
	var result strings.Builder
	for _, line := range source.preamble {
		result.WriteString(line)
		result.WriteByte('\n')
	}
	for _, name := range names {
		result.WriteString(name)
		result.WriteString("='")
		result.WriteString(encodeValue(source.entries[name])[1:])
		result.WriteByte('\n')
	}
	return []byte(result.String())
}

func encodeValue(value string) string {
	return "'" + strings.ReplaceAll(value, "'", "'\\''") + "'"
}
