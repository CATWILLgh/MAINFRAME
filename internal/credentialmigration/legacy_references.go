package credentialmigration

import (
	"bufio"
	"bytes"
	"errors"
	"fmt"
	"io/fs"
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type ReferenceCompatibility string

const (
	ReferenceCatalogCompatible ReferenceCompatibility = "catalog_compatible"
	ReferenceLegacyName        ReferenceCompatibility = "legacy_name"
)

type LegacyReferencePreview struct {
	Groups                     []LegacyReferenceGroup
	Sections                   []LegacySectionAccounting
	TotalReferenceMentions     int
	ExtractedReferenceMentions int
	ExcludedReferenceMentions  int
	ExcludedExampleMentions    int
	MalformedReferenceMentions int
	UnscopedReferenceMentions  int
	UnmappedContentLines       int
	InvalidHeadingLines        int
	ExcludedContentLines       int
}

type LegacySectionAccounting struct {
	SectionPath          []string
	UnmappedContentLines int
}

type LegacyReferenceInventory struct {
	ReleaseID          string
	ReleaseIndexSHA256 string
	MigrationReadiness Readiness
	Indexes            []LegacyIndex
	References         LegacyReferencePreview
}

type LegacyReferenceGroup struct {
	SectionPath          []string
	References           []LegacyReference
	UnmappedContentLines int
}

type LegacyReference struct {
	Name          string
	Occurrences   int
	Compatibility ReferenceCompatibility
}

var (
	legacyHeadingPattern            = regexp.MustCompile(`^(#{1,6})[ \t]+(.+?)[ \t]*$`)
	legacyMentionPattern            = regexp.MustCompile(`\bsecret[ \t]+get\b`)
	legacyNamePattern               = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_-]*$`)
	legacyExactReferenceLinePattern = regexp.MustCompile(
		"^[ \\t]*(?:[-*][ \\t]+)?`?secret[ \\t]+get[ \\t]+" +
			"[A-Za-z_][A-Za-z0-9_-]*`?[.,;:!?]?[ \\t]*$",
	)
)

const maxLegacyReferenceLineBytes = 1 << 20

func InspectLegacyReferencePreview(
	release releasecontract.Release,
	inspector Inspector,
) (LegacyReferenceInventory, error) {
	resources, err := legacyResources(release.Resources)
	if err != nil {
		return LegacyReferenceInventory{}, err
	}
	indexes := make([]LegacyIndex, len(resources))
	var references LegacyReferencePreview
	indexes[0], references = inspectLegacyReferenceSource(
		resources[0],
		inspector,
	)
	for index := 1; index < len(resources); index++ {
		indexes[index] = inspectLegacyIndex(
			resources[index],
			legacyResourceDescriptors[index].sourceRole,
			inspector,
		)
	}
	return LegacyReferenceInventory{
		ReleaseID: release.ID, ReleaseIndexSHA256: release.IndexSHA256,
		MigrationReadiness: reduceReadiness(indexes),
		Indexes:            indexes,
		References:         references,
	}, nil
}

func inspectLegacyReferenceSource(
	resource releasecontract.Resource,
	inspector Inspector,
) (LegacyIndex, LegacyReferencePreview) {
	source := LegacyIndex{
		ComponentID: resource.ComponentID,
		ResourceID:  resource.ID,
		Location:    resource.Target,
		SourceRole:  SourceRoleSharedOriginal,
	}
	entry, err := inspector.Inspect(resource.Target, true)
	if errors.Is(err, fs.ErrNotExist) {
		source.State = IndexMissing
		return legacyIndexWithReadiness(source), LegacyReferencePreview{}
	}
	if err != nil {
		source.State = IndexUnsafe
		source.UnsafeReason = ReasonInspectionFailed
		return legacyIndexWithReadiness(source), LegacyReferencePreview{}
	}
	if reason := legacyEntryUnsafeReason(entry); reason != "" {
		source.State = IndexUnsafe
		source.UnsafeReason = reason
		return legacyIndexWithReadiness(source), LegacyReferencePreview{}
	}
	source.State = IndexPresent
	source.SizeBytes = len(entry.Content)
	source.MatchesCurrentTemplate = bytes.Equal(
		entry.Content,
		resource.SourceContent,
	)
	source = legacyIndexWithReadiness(source)
	if source.MigrationReadiness != ReadinessManualTransferRequired {
		return source, LegacyReferencePreview{}
	}
	preview, err := PreviewLegacyReferences(entry.Content)
	if err != nil {
		source.State = IndexUnsafe
		source.UnsafeReason = ReasonMalformedContent
		source.MatchesCurrentTemplate = false
		return legacyIndexWithReadiness(source), LegacyReferencePreview{}
	}
	return source, preview
}

func legacyEntryUnsafeReason(entry hostfs.Entry) UnsafeReason {
	switch {
	case entry.Kind == hostfs.EntrySymlink:
		return ReasonSymbolicLink
	case entry.Kind != hostfs.EntryRegular:
		return ReasonNotRegular
	case entry.Mode != 0o600:
		return ReasonUnsafeMode
	default:
		return ""
	}
}

func PreviewLegacyReferences(content []byte) (LegacyReferencePreview, error) {
	if !utf8.Valid(content) || bytes.IndexByte(content, 0) >= 0 {
		return LegacyReferencePreview{}, fmt.Errorf(
			"legacy credential catalog is not safe text",
		)
	}
	builder := legacyPreviewBuilder{
		groupIndexes:     make(map[string]int),
		referenceIndexes: make(map[int]map[string]int),
		unmappedByPath:   make(map[string]int),
	}
	scanner := bufio.NewScanner(bytes.NewReader(content))
	scanner.Buffer(make([]byte, 4096), maxLegacyReferenceLineBytes)
	for scanner.Scan() {
		builder.consumeLine(scanner.Text())
	}
	if err := scanner.Err(); err != nil {
		return LegacyReferencePreview{}, fmt.Errorf(
			"scan legacy credential catalog: %w",
			err,
		)
	}
	builder.finalizeSectionAccounting()
	return builder.preview, nil
}

type legacyPreviewBuilder struct {
	preview          LegacyReferencePreview
	headings         [6]string
	inHTMLComment    bool
	inFence          bool
	fenceMarker      string
	groupIndexes     map[string]int
	referenceIndexes map[int]map[string]int
	unmappedByPath   map[string]int
	sectionOrder     []string
}

func (builder *legacyPreviewBuilder) consumeLine(line string) {
	trimmed := strings.TrimSpace(line)
	example := builder.lineIsExample(trimmed)
	if example && meaningfulLegacyContent(trimmed) {
		builder.preview.ExcludedContentLines++
	}
	heading := false
	if !example {
		heading = builder.consumeHeading(trimmed)
	}
	mentions := legacyMentionPattern.FindAllStringIndex(line, -1)
	for _, bounds := range mentions {
		builder.preview.TotalReferenceMentions++
		name := legacyReferenceName(line[bounds[1]:])
		if example {
			builder.preview.ExcludedReferenceMentions++
			builder.preview.ExcludedExampleMentions++
			continue
		}
		if name == "" {
			builder.preview.ExcludedReferenceMentions++
			builder.preview.MalformedReferenceMentions++
			continue
		}
		if len(builder.sectionPath()) == 0 {
			builder.preview.ExcludedReferenceMentions++
			builder.preview.UnscopedReferenceMentions++
			continue
		}
		builder.addReference(name)
		builder.preview.ExtractedReferenceMentions++
	}
	if !example && !heading && meaningfulLegacyContent(trimmed) &&
		(len(mentions) == 0 ||
			!legacyExactReferenceLinePattern.MatchString(line)) {
		builder.preview.UnmappedContentLines++
		builder.addUnmappedContent()
	}
	builder.updateHTMLCommentState(line)
}

func (builder *legacyPreviewBuilder) lineIsExample(trimmed string) bool {
	if marker := fenceMarker(trimmed); marker != "" {
		if builder.inFence && marker == builder.fenceMarker {
			builder.inFence = false
			builder.fenceMarker = ""
		} else if !builder.inFence {
			builder.inFence = true
			builder.fenceMarker = marker
		}
		return true
	}
	return builder.inFence ||
		builder.inHTMLComment ||
		strings.HasPrefix(trimmed, ">") ||
		strings.Contains(trimmed, "<!--")
}

func (builder *legacyPreviewBuilder) consumeHeading(line string) bool {
	match := legacyHeadingPattern.FindStringSubmatch(line)
	if match == nil {
		return false
	}
	level := len(match[1])
	title := strings.TrimSpace(strings.TrimRight(match[2], "#"))
	if !validLegacyHeading(title) {
		builder.preview.InvalidHeadingLines++
		builder.headings[level-1] = ""
		for index := level; index < len(builder.headings); index++ {
			builder.headings[index] = ""
		}
		return true
	}
	builder.headings[level-1] = title
	for index := level; index < len(builder.headings); index++ {
		builder.headings[index] = ""
	}
	return true
}

func (builder *legacyPreviewBuilder) addUnmappedContent() {
	path := builder.sectionPath()
	if len(path) == 0 {
		return
	}
	key := strings.Join(path, "\x00")
	if _, exists := builder.unmappedByPath[key]; !exists {
		builder.sectionOrder = append(builder.sectionOrder, key)
	}
	builder.unmappedByPath[key]++
	if groupIndex, exists := builder.groupIndexes[key]; exists {
		builder.preview.Groups[groupIndex].UnmappedContentLines++
	}
}

func (builder *legacyPreviewBuilder) finalizeSectionAccounting() {
	builder.preview.Sections = make(
		[]LegacySectionAccounting,
		0,
		len(builder.sectionOrder),
	)
	for _, key := range builder.sectionOrder {
		builder.preview.Sections = append(
			builder.preview.Sections,
			LegacySectionAccounting{
				SectionPath:          strings.Split(key, "\x00"),
				UnmappedContentLines: builder.unmappedByPath[key],
			},
		)
	}
}

func validLegacyHeading(title string) bool {
	if title == "" || utf8.RuneCountInString(title) > 240 {
		return false
	}
	for _, character := range title {
		if unicode.IsControl(character) || unicode.In(character, unicode.Cf) {
			return false
		}
	}
	return true
}

func (builder *legacyPreviewBuilder) updateHTMLCommentState(line string) {
	position := 0
	for position < len(line) {
		if builder.inHTMLComment {
			end := strings.Index(line[position:], "-->")
			if end < 0 {
				return
			}
			builder.inHTMLComment = false
			position += end + len("-->")
			continue
		}
		start := strings.Index(line[position:], "<!--")
		if start < 0 {
			return
		}
		builder.inHTMLComment = true
		position += start + len("<!--")
	}
}

func (builder *legacyPreviewBuilder) sectionPath() []string {
	path := make([]string, 0, len(builder.headings))
	for _, heading := range builder.headings {
		if heading != "" {
			path = append(path, heading)
		}
	}
	return path
}

func (builder *legacyPreviewBuilder) addReference(name string) {
	path := builder.sectionPath()
	key := strings.Join(path, "\x00")
	groupIndex, exists := builder.groupIndexes[key]
	if !exists {
		groupIndex = len(builder.preview.Groups)
		builder.groupIndexes[key] = groupIndex
		builder.referenceIndexes[groupIndex] = make(map[string]int)
		builder.preview.Groups = append(
			builder.preview.Groups,
			LegacyReferenceGroup{
				SectionPath:          path,
				UnmappedContentLines: builder.unmappedByPath[key],
			},
		)
	}
	referenceIndexes := builder.referenceIndexes[groupIndex]
	referenceIndex, exists := referenceIndexes[name]
	if exists {
		builder.preview.Groups[groupIndex].References[referenceIndex].Occurrences++
		return
	}
	referenceIndexes[name] = len(builder.preview.Groups[groupIndex].References)
	builder.preview.Groups[groupIndex].References = append(
		builder.preview.Groups[groupIndex].References,
		LegacyReference{
			Name: name, Occurrences: 1,
			Compatibility: legacyReferenceCompatibility(name),
		},
	)
}

func legacyReferenceName(remainder string) string {
	remainder = strings.TrimLeft(remainder, " \t")
	if remainder == "" {
		return ""
	}
	end := strings.IndexAny(remainder, " \t`\"'")
	if end < 0 {
		end = len(remainder)
	}
	token := strings.TrimRight(remainder[:end], ".,;:!?)]}")
	if !legacyNamePattern.MatchString(token) {
		return ""
	}
	return token
}

func legacyReferenceCompatibility(name string) ReferenceCompatibility {
	err := credentialcatalog.ValidateSecretReference(
		credentialcatalog.SecretReference{
			Backend: credentialcatalog.BackendSecretEnvironment,
			Name:    name,
		},
	)
	if err == nil {
		return ReferenceCatalogCompatible
	}
	return ReferenceLegacyName
}

func fenceMarker(line string) string {
	switch {
	case strings.HasPrefix(line, "```"):
		return "```"
	case strings.HasPrefix(line, "~~~"):
		return "~~~"
	default:
		return ""
	}
}

func meaningfulLegacyContent(line string) bool {
	if line == "" {
		return false
	}
	for _, character := range line {
		if character != '-' && character != '_' && character != '*' {
			return true
		}
	}
	return false
}
