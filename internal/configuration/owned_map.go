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

type ownedMapReconciliation struct {
	merged         any
	nextOwned      map[string]any
	mergedOrder    map[string]string
	nextOwnedOrder map[string]string
	mergedRaw      string
	nextOwnedRaw   string
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
	result, err := reconcileOwnedMapWithOrder(
		existing,
		generated,
		owned,
		map[string]string{},
		map[string]string{},
		map[string]string{},
	)
	return result.merged, result.nextOwned, err
}

func reconcileOwnedJSONMaps(
	existingRaw, generatedRaw, ownedRaw string,
) (ownedMapReconciliation, error) {
	existing, err := decodeDecisionValue(existingRaw)
	if err != nil {
		return ownedMapReconciliation{}, err
	}
	generated, err := decodeDecisionMap(generatedRaw, false)
	if err != nil {
		return ownedMapReconciliation{}, err
	}
	owned, err := decodeDecisionMap(ownedRaw, true)
	if err != nil {
		return ownedMapReconciliation{}, err
	}
	existingOrder, err := orderedRuleMap(existingRaw)
	if err != nil {
		return ownedMapReconciliation{}, err
	}
	generatedOrder, err := orderedRuleMap(generatedRaw)
	if err != nil {
		return ownedMapReconciliation{}, err
	}
	ownedOrder, err := orderedRuleMap(ownedRaw)
	if err != nil {
		return ownedMapReconciliation{}, err
	}
	result, err := reconcileOwnedMapWithOrder(
		existing,
		generated,
		owned,
		existingOrder,
		generatedOrder,
		ownedOrder,
	)
	if err != nil {
		return ownedMapReconciliation{}, err
	}
	result.mergedRaw, err = encodeMergedDecision(
		result.merged,
		result.mergedOrder,
		existingRaw,
		generatedRaw,
	)
	if err != nil {
		return ownedMapReconciliation{}, err
	}
	result.nextOwnedRaw, err = encodeOrderedDecisionMap(
		result.nextOwned,
		result.nextOwnedOrder,
		ownedRaw,
		existingRaw,
		generatedRaw,
	)
	if err != nil {
		return ownedMapReconciliation{}, err
	}
	return result, nil
}

func reconcileOwnedMapWithOrder(
	existing any,
	generated, owned map[string]any,
	existingOrder, generatedOrder, ownedOrder map[string]string,
) (ownedMapReconciliation, error) {
	if err := validateDecisionMap(existing, false); err != nil {
		return ownedMapReconciliation{}, fmt.Errorf("existing map: %w", err)
	}
	if err := validateDecisionMap(generated, false); err != nil {
		return ownedMapReconciliation{}, fmt.Errorf("generated map: %w", err)
	}
	if err := validateDecisionMap(owned, true); err != nil {
		return ownedMapReconciliation{}, fmt.Errorf("ownership map: %w", err)
	}
	existingMap, isMap := existing.(map[string]any)
	if !isMap {
		return ownedMapReconciliation{
			merged:         existing,
			nextOwned:      tombstoneAll(owned, generated),
			mergedOrder:    map[string]string{},
			nextOwnedOrder: map[string]string{},
		}, nil
	}
	result := ownedMapReconciliation{
		merged:         cloneDecisionMap(existingMap),
		mergedOrder:    cloneRuleOrder(existingOrder),
		nextOwnedOrder: map[string]string{},
	}
	merged := result.merged.(map[string]any)
	result.nextOwned = reconcilePreviouslyOwned(
		existingMap, generated, owned, merged,
		existingOrder, generatedOrder, ownedOrder,
		result.mergedOrder, result.nextOwnedOrder,
	)
	for action := range existingMap {
		if _, tracked := owned[action]; !tracked {
			result.nextOwned[action] = nil
		}
	}
	addGeneratedActions(
		generated, merged, result.nextOwned,
		generatedOrder, result.mergedOrder, result.nextOwnedOrder,
	)
	return result, nil
}

func reconcilePreviouslyOwned(
	existing, generated, owned, merged map[string]any,
	existingOrder, generatedOrder, ownedOrder map[string]string,
	mergedOrder, nextOwnedOrder map[string]string,
) map[string]any {
	next := make(map[string]any, len(owned)+len(generated))
	for action, previous := range owned {
		actual, exists := existing[action]
		switch {
		case previous == nil:
			next[action] = nil
		case !exists || !decisionRulesEqual(
			actual, previous, existingOrder[action], ownedOrder[action],
		):
			next[action] = nil
		case generated[action] != nil:
			merged[action] = cloneDecisionRule(generated[action])
			next[action] = cloneDecisionRule(generated[action])
			copyRuleOrder(action, generatedOrder, mergedOrder)
			copyRuleOrder(action, generatedOrder, nextOwnedOrder)
		default:
			delete(merged, action)
			delete(mergedOrder, action)
		}
	}
	return next
}

func addGeneratedActions(
	generated, merged, nextOwned map[string]any,
	generatedOrder, mergedOrder, nextOwnedOrder map[string]string,
) {
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
		copyRuleOrder(action, generatedOrder, mergedOrder)
		copyRuleOrder(action, generatedOrder, nextOwnedOrder)
	}
}

func decisionRulesEqual(actual, previous any, actualOrder, previousOrder string) bool {
	if !reflect.DeepEqual(actual, previous) {
		return false
	}
	_, nested := actual.(map[string]any)
	return !nested || actualOrder == previousOrder
}

func copyRuleOrder(action string, source, target map[string]string) {
	if order, present := source[action]; present {
		target[action] = order
	} else {
		delete(target, action)
	}
}

func cloneRuleOrder(source map[string]string) map[string]string {
	result := make(map[string]string, len(source))
	for action, order := range source {
		result[action] = order
	}
	return result
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
