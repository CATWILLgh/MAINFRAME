package discovery

import (
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func observedState(grouped map[domain.ComponentID][]domain.Artifact) domain.ObservedState {
	ids := make([]domain.ComponentID, 0, len(grouped))
	for id := range grouped {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	components := make([]domain.ObservedComponent, 0, len(ids))
	for _, id := range ids {
		artifacts := grouped[id]
		sort.Slice(artifacts, func(i, j int) bool {
			if artifacts[i].Location.Root != artifacts[j].Location.Root {
				return artifacts[i].Location.Root < artifacts[j].Location.Root
			}
			return artifacts[i].Location.Path < artifacts[j].Location.Path
		})
		components = append(components, domain.ObservedComponent{ID: id, Artifacts: artifacts})
	}
	return domain.ObservedState{Components: components}
}
