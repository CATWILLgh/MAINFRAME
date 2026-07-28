package domain

import "regexp"

var unitIDPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[._/-][a-z0-9_]+)*$`)

func ValidUnitID(value string) bool {
	return unitIDPattern.MatchString(value)
}
