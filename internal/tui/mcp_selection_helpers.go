package tui

import (
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func defaultProfile(server mcpcatalog.Server) mcpcatalog.ProfileID {
	for _, profile := range server.Profiles {
		if profile.Authentication.Kind == mcpcatalog.AuthenticationNone {
			return profile.ID
		}
	}
	return server.Profiles[0].ID
}

func supportedSubset(
	selected []domain.ComponentID,
	profile mcpcatalog.Profile,
) []domain.ComponentID {
	result := make([]domain.ComponentID, 0, len(selected))
	for _, adapter := range selected {
		if status, _ := profile.Support(adapter); status == mcpcatalog.Supported {
			result = append(result, adapter)
		}
	}
	return result
}

func selectedSubset(
	chosen []domain.ComponentID,
	selected []domain.ComponentID,
) []domain.ComponentID {
	result := make([]domain.ComponentID, 0, len(chosen))
	for _, adapter := range chosen {
		if contains(selected, adapter) {
			result = append(result, adapter)
		}
	}
	return result
}

func verifiedOn(server mcpcatalog.Server) string {
	dates := make([]string, 0, len(server.Profiles))
	for _, profile := range server.Profiles {
		dates = append(dates, profile.Evidence.VerifiedOn)
	}
	sort.Strings(dates)
	return dates[len(dates)-1]
}

func authenticationName(kind mcpcatalog.AuthenticationKind) string {
	if kind == mcpcatalog.AuthenticationAPIKey {
		return "API key"
	}
	return "no key"
}
