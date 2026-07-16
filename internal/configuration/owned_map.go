package configuration

import (
	"encoding/json"
	"fmt"
	"reflect"
	"regexp"
	"runtime"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

var decisions = map[string]bool{
	"allow": true,
	"ask":   true,
	"deny":  true,
}

func decodeDecisionValue(raw string) (any, error) {
	document, err := jsondocument.Parse([]byte(raw))
	if err != nil {
		return nil, err
	}
	var value any
	if err := json.Unmarshal([]byte(document.Canonical()), &value); err != nil {
		return nil, err
	}
	return value, nil
}

func decodeDecisionMap(raw string, allowNull bool) (map[string]any, error) {
	value, err := decodeDecisionValue(raw)
	if err != nil {
		return nil, err
	}
	entries, valid := value.(map[string]any)
	if !valid {
		return nil, fmt.Errorf("expected an action map")
	}
	if err := validateDecisionMap(entries, allowNull); err != nil {
		return nil, err
	}
	return entries, nil
}

func reconcileOwnedMap(
	existing any,
	generated map[string]any,
	owned map[string]any,
) (any, map[string]any, error) {
	if err := validateDecisionMap(existing, false); err != nil {
		return nil, nil, fmt.Errorf("existing map: %w", err)
	}
	if err := validateDecisionMap(generated, false); err != nil {
		return nil, nil, fmt.Errorf("generated map: %w", err)
	}
	if err := validateDecisionMap(owned, true); err != nil {
		return nil, nil, fmt.Errorf("ownership map: %w", err)
	}
	existingMap, isMap := existing.(map[string]any)
	if !isMap {
		return existing, tombstoneAll(owned, generated), nil
	}
	merged := cloneDecisionMap(existingMap)
	nextOwned := reconcilePreviouslyOwned(existingMap, generated, owned, merged)
	for action := range existingMap {
		if _, tracked := owned[action]; !tracked {
			nextOwned[action] = nil
		}
	}
	addGeneratedActions(generated, merged, nextOwned)
	return merged, nextOwned, nil
}

func reconcilePreviouslyOwned(
	existing, generated, owned, merged map[string]any,
) map[string]any {
	next := make(map[string]any, len(owned)+len(generated))
	for action, previous := range owned {
		actual, exists := existing[action]
		switch {
		case previous == nil:
			next[action] = nil
		case !exists || !reflect.DeepEqual(actual, previous):
			next[action] = nil
		case generated[action] != nil:
			merged[action] = cloneDecisionRule(generated[action])
			next[action] = cloneDecisionRule(generated[action])
		default:
			delete(merged, action)
		}
	}
	return next
}

func addGeneratedActions(generated, merged, nextOwned map[string]any) {
	actions := sortedKeys(generated)
	for _, action := range actions {
		if _, tracked := nextOwned[action]; tracked {
			continue
		}
		if _, exists := merged[action]; exists {
			continue
		}
		if existingPatternMatches(action, merged) {
			nextOwned[action] = nil
			continue
		}
		merged[action] = cloneDecisionRule(generated[action])
		nextOwned[action] = cloneDecisionRule(generated[action])
	}
}

func validateDecisionMap(value any, allowNull bool) error {
	if decision, scalar := value.(string); scalar {
		if decisions[decision] {
			return nil
		}
		return fmt.Errorf("invalid decision %q", decision)
	}
	entries, valid := value.(map[string]any)
	if !valid {
		return fmt.Errorf("expected a decision or action map")
	}
	for action, rule := range entries {
		if action == "" || (rule == nil && !allowNull) || !validDecisionRule(rule, allowNull) {
			return fmt.Errorf("invalid action %q", action)
		}
	}
	return nil
}

func validDecisionRule(value any, allowNull bool) bool {
	if value == nil {
		return allowNull
	}
	if decision, scalar := value.(string); scalar {
		return decisions[decision]
	}
	patterns, valid := value.(map[string]any)
	if !valid || len(patterns) == 0 {
		return false
	}
	for pattern, decision := range patterns {
		verdict, scalar := decision.(string)
		if pattern == "" || !scalar || !decisions[verdict] {
			return false
		}
	}
	return true
}

func tombstoneAll(owned, generated map[string]any) map[string]any {
	result := make(map[string]any, len(owned)+len(generated))
	for action := range owned {
		result[action] = nil
	}
	for action := range generated {
		result[action] = nil
	}
	return result
}

func existingPatternMatches(action string, existing map[string]any) bool {
	for pattern := range existing {
		if actionMatchesPattern(action, pattern) {
			return true
		}
	}
	return false
}

func actionMatchesPattern(action, pattern string) bool {
	pattern = strings.ReplaceAll(pattern, "\\", "/")
	action = strings.ReplaceAll(action, "\\", "/")
	var expression strings.Builder
	for _, character := range pattern {
		switch character {
		case '*':
			expression.WriteString(".*")
		case '?':
			expression.WriteByte('.')
		default:
			expression.WriteString(regexp.QuoteMeta(string(character)))
		}
	}
	raw := expression.String()
	if strings.HasSuffix(raw, " .*") {
		raw = strings.TrimSuffix(raw, " .*") + "( .*)?"
	}
	flags := "(?s)"
	if runtime.GOOS == "windows" {
		flags = "(?si)"
	}
	matched, err := regexp.MatchString(flags+"^(?:"+raw+")$", action)
	return err == nil && matched
}

func cloneDecisionMap(source map[string]any) map[string]any {
	result := make(map[string]any, len(source))
	for key, value := range source {
		result[key] = cloneDecisionRule(value)
	}
	return result
}

func cloneDecisionRule(value any) any {
	patterns, nested := value.(map[string]any)
	if !nested {
		return value
	}
	return cloneDecisionMap(patterns)
}

func sortedKeys(values map[string]any) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}
