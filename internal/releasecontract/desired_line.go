package releasecontract

import (
	"fmt"
	"strings"
	"unicode"
	"unicode/utf8"
)

func loadDesiredLine(
	bundleRoot, source string,
	strategy ResourceStrategy,
	support SupportStatus,
) (string, error) {
	if support != SupportSupported ||
		(strategy != StrategyShellLine && strategy != StrategyShellLineIfPresent) {
		return "", nil
	}
	payload, err := readRegular(bundleRoot, source)
	if err != nil {
		return "", err
	}
	if !utf8.Valid(payload) {
		return "", fmt.Errorf("shell source must be valid UTF-8")
	}
	line := strings.TrimSuffix(string(payload), "\n")
	if strings.Trim(line, " \t") == "" ||
		strings.ContainsAny(line, "\r\n") ||
		hasUnsupportedShellControl(line) {
		return "", fmt.Errorf("shell source must contain exactly one non-empty line")
	}
	return line, nil
}

func hasUnsupportedShellControl(line string) bool {
	for _, character := range line {
		if character != '\t' && unicode.IsControl(character) {
			return true
		}
	}
	return false
}
