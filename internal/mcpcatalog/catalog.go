package mcpcatalog

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

const (
	catalogSchemaVersion = 1
	catalogKind          = "mainframe-mcp-catalog"
)

var identifierPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`)
var repositorySegmentPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]*$`)

type ServerID string
type ProfileID string
type Transport string
type AuthenticationKind string
type AuthenticationPlacement string
type CompatibilityStatus string

const (
	TransportStreamableHTTP Transport = "streamable-http"
	TransportStdio          Transport = "stdio"

	AuthenticationNone   AuthenticationKind = "none"
	AuthenticationAPIKey AuthenticationKind = "api-key"

	PlacementNone   AuthenticationPlacement = "none"
	PlacementHeader AuthenticationPlacement = "header"

	Supported   CompatibilityStatus = "supported"
	Unsupported CompatibilityStatus = "unsupported"
)

type Catalog struct {
	servers []Server
}

type Server struct {
	ID               ServerID   `json:"id"`
	Name             string     `json:"name"`
	Summary          string     `json:"summary"`
	Publisher        string     `json:"publisher"`
	HomepageURL      string     `json:"homepage_url"`
	DocumentationURL string     `json:"documentation_url"`
	Repository       Repository `json:"repository"`
	License          string     `json:"license"`
	Profiles         []Profile  `json:"profiles"`
}

type Repository struct {
	Owner string `json:"owner"`
	Name  string `json:"name"`
	URL   string `json:"url"`
}

type Profile struct {
	ID                ProfileID              `json:"id"`
	Name              string                 `json:"name"`
	Transport         Transport              `json:"transport"`
	Endpoint          string                 `json:"endpoint,omitempty"`
	Command           []string               `json:"command,omitempty"`
	Authentication    Authentication         `json:"authentication"`
	ServiceCredential *ServiceCredential     `json:"service_credential,omitempty"`
	Compatibility     []AdapterCompatibility `json:"compatibility"`
	Evidence          Evidence               `json:"evidence"`
}

type Authentication struct {
	Kind                AuthenticationKind      `json:"kind"`
	Placement           AuthenticationPlacement `json:"placement"`
	EnvironmentVariable string                  `json:"environment_variable"`
}

type ServiceCredential struct {
	Kind                AuthenticationKind `json:"kind"`
	EnvironmentVariable string             `json:"environment_variable"`
}

type AdapterCompatibility struct {
	Adapter domain.ComponentID  `json:"adapter"`
	Status  CompatibilityStatus `json:"status"`
	Reason  string              `json:"reason"`
}

type Evidence struct {
	URL        string `json:"url"`
	VerifiedOn string `json:"verified_on"`
}

type catalogDocument struct {
	SchemaVersion int      `json:"schema_version"`
	Kind          string   `json:"kind"`
	Servers       []Server `json:"servers"`
}

func Parse(payload []byte) (Catalog, error) {
	if _, err := jsondocument.Parse(payload); err != nil {
		return Catalog{}, fmt.Errorf("validate catalog JSON: %w", err)
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	var document catalogDocument
	if err := decoder.Decode(&document); err != nil {
		return Catalog{}, fmt.Errorf("decode catalog: %w", err)
	}
	var trailing json.RawMessage
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		return Catalog{}, fmt.Errorf("catalog must contain one JSON document")
	}
	if err := validateDocument(document); err != nil {
		return Catalog{}, err
	}
	return Catalog{servers: cloneServers(document.Servers)}, nil
}

func (catalog Catalog) Servers() []Server {
	return cloneServers(catalog.servers)
}

func (catalog Catalog) Server(id ServerID) (Server, bool) {
	for _, server := range catalog.servers {
		if server.ID == id {
			return cloneServer(server), true
		}
	}
	return Server{}, false
}

func (server Server) Profile(id ProfileID) (Profile, bool) {
	for _, profile := range server.Profiles {
		if profile.ID == id {
			return cloneProfile(profile), true
		}
	}
	return Profile{}, false
}

func (profile Profile) Support(adapter domain.ComponentID) (CompatibilityStatus, string) {
	for _, compatibility := range profile.Compatibility {
		if compatibility.Adapter == adapter {
			return compatibility.Status, compatibility.Reason
		}
	}
	return Unsupported, "adapter is absent from the verified profile"
}

func validateDocument(document catalogDocument) error {
	if document.SchemaVersion != catalogSchemaVersion || document.Kind != catalogKind {
		return fmt.Errorf("unsupported MCP catalog contract")
	}
	if len(document.Servers) == 0 {
		return fmt.Errorf("MCP catalog must contain at least one server")
	}
	ids := make([]string, len(document.Servers))
	for index, server := range document.Servers {
		ids[index] = string(server.ID)
		if err := validateServer(server); err != nil {
			return fmt.Errorf("server %q: %w", server.ID, err)
		}
	}
	if !sortedUnique(ids) {
		return fmt.Errorf("MCP servers must be sorted with unique ids")
	}
	return nil
}

func validateServer(server Server) error {
	if !identifierPattern.MatchString(string(server.ID)) ||
		server.Name == "" || server.Summary == "" || server.Publisher == "" || server.License == "" {
		return fmt.Errorf("invalid server identity or descriptive metadata")
	}
	for label, value := range map[string]string{
		"homepage":      server.HomepageURL,
		"documentation": server.DocumentationURL,
	} {
		if err := validateHTTPSURL(value); err != nil {
			return fmt.Errorf("invalid %s URL: %w", label, err)
		}
	}
	if err := validateRepository(server.Repository); err != nil {
		return err
	}
	if len(server.Profiles) == 0 {
		return fmt.Errorf("server must contain at least one profile")
	}
	ids := make([]string, len(server.Profiles))
	for index, profile := range server.Profiles {
		ids[index] = string(profile.ID)
		if err := validateProfile(profile); err != nil {
			return fmt.Errorf("profile %q: %w", profile.ID, err)
		}
	}
	if !sortedUnique(ids) {
		return fmt.Errorf("profiles must be sorted with unique ids")
	}
	return nil
}

func validateRepository(repository Repository) error {
	if !repositorySegmentPattern.MatchString(repository.Owner) ||
		!repositorySegmentPattern.MatchString(repository.Name) {
		return fmt.Errorf("invalid repository identity")
	}
	parsed, err := url.ParseRequestURI(repository.URL)
	if err != nil || parsed.Scheme != "https" ||
		!strings.EqualFold(parsed.Hostname(), "github.com") ||
		parsed.RawQuery != "" || parsed.Fragment != "" {
		return fmt.Errorf("repository must use a canonical GitHub HTTPS URL")
	}
	expected := "/" + repository.Owner + "/" + repository.Name
	if !strings.EqualFold(strings.TrimSuffix(parsed.Path, "/"), expected) {
		return fmt.Errorf("repository URL does not match its owner and name")
	}
	return nil
}

func validateProfile(profile Profile) error {
	if !identifierPattern.MatchString(string(profile.ID)) || profile.Name == "" {
		return fmt.Errorf("invalid profile identity")
	}
	if err := validateTransport(profile); err != nil {
		return err
	}
	if err := validateAuthentication(profile.Authentication); err != nil {
		return err
	}
	if profile.ServiceCredential != nil {
		if err := validateServiceCredential(*profile.ServiceCredential); err != nil {
			return err
		}
	}
	if err := validateCompatibility(profile.Compatibility); err != nil {
		return err
	}
	if err := validateHTTPSURL(profile.Evidence.URL); err != nil {
		return fmt.Errorf("invalid evidence URL: %w", err)
	}
	if _, err := time.Parse(time.DateOnly, profile.Evidence.VerifiedOn); err != nil {
		return fmt.Errorf("invalid evidence verification date")
	}
	return nil
}

func validateTransport(profile Profile) error {
	switch profile.Transport {
	case TransportStreamableHTTP:
		if len(profile.Command) != 0 {
			return fmt.Errorf("HTTP profile must not contain a command")
		}
		if err := validateHTTPSURL(profile.Endpoint); err != nil {
			return fmt.Errorf("invalid HTTP endpoint: %w", err)
		}
	case TransportStdio:
		if profile.Endpoint != "" || len(profile.Command) == 0 {
			return fmt.Errorf("stdio profile requires only a command")
		}
		for _, argument := range profile.Command {
			if argument == "" {
				return fmt.Errorf("stdio command arguments must not be empty")
			}
		}
	default:
		return fmt.Errorf("unsupported transport %q", profile.Transport)
	}
	return nil
}

func validateAuthentication(authentication Authentication) error {
	switch authentication.Kind {
	case AuthenticationNone:
		if authentication.Placement != PlacementNone || authentication.EnvironmentVariable != "" {
			return fmt.Errorf("keyless authentication must not name secret placement")
		}
	case AuthenticationAPIKey:
		if authentication.Placement != PlacementHeader ||
			!validEnvironmentVariable(authentication.EnvironmentVariable) {
			return fmt.Errorf("API-key authentication requires a header environment variable")
		}
	default:
		return fmt.Errorf("unsupported authentication kind %q", authentication.Kind)
	}
	return nil
}

func validateServiceCredential(credential ServiceCredential) error {
	if credential.Kind != AuthenticationAPIKey ||
		!validEnvironmentVariable(credential.EnvironmentVariable) {
		return fmt.Errorf("service credential must be an API-key environment variable")
	}
	return nil
}

func validateCompatibility(entries []AdapterCompatibility) error {
	if len(entries) != 4 {
		return fmt.Errorf("profile compatibility must classify every adapter")
	}
	ids := make([]string, len(entries))
	for index, entry := range entries {
		ids[index] = string(entry.Adapter)
		if !knownAdapter(entry.Adapter) {
			return fmt.Errorf("unknown adapter %q", entry.Adapter)
		}
		if (entry.Status == Supported && entry.Reason != "") ||
			(entry.Status == Unsupported && entry.Reason == "") {
			return fmt.Errorf("adapter %q has inconsistent support reason", entry.Adapter)
		}
		if entry.Status != Supported && entry.Status != Unsupported {
			return fmt.Errorf("adapter %q has invalid support status", entry.Adapter)
		}
	}
	if !sortedUnique(ids) {
		return fmt.Errorf("compatibility must be sorted with unique adapters")
	}
	return nil
}

func knownAdapter(id domain.ComponentID) bool {
	switch id {
	case domain.ComponentClaudeCode,
		domain.ComponentCodex,
		domain.ComponentOpenCode,
		domain.ComponentAntigravity2:
		return true
	default:
		return false
	}
}

func validateHTTPSURL(raw string) error {
	parsed, err := url.ParseRequestURI(raw)
	if err != nil || parsed.Scheme != "https" || parsed.Host == "" || parsed.User != nil {
		return fmt.Errorf("must be an absolute HTTPS URL")
	}
	return nil
}

func validEnvironmentVariable(value string) bool {
	matched, _ := regexp.MatchString(`^[A-Z_][A-Z0-9_]*$`, value)
	return matched
}

func sortedUnique(values []string) bool {
	return sort.StringsAreSorted(values) && len(values) == len(uniqueStrings(values))
}

func uniqueStrings(values []string) map[string]struct{} {
	result := make(map[string]struct{}, len(values))
	for _, value := range values {
		result[value] = struct{}{}
	}
	return result
}

func cloneServers(servers []Server) []Server {
	cloned := make([]Server, len(servers))
	for index, server := range servers {
		cloned[index] = cloneServer(server)
	}
	return cloned
}

func cloneServer(server Server) Server {
	profiles := server.Profiles
	server.Profiles = make([]Profile, len(profiles))
	for index, profile := range profiles {
		server.Profiles[index] = cloneProfile(profile)
	}
	return server
}

func cloneProfile(profile Profile) Profile {
	profile.Command = append([]string(nil), profile.Command...)
	profile.Compatibility = append([]AdapterCompatibility(nil), profile.Compatibility...)
	if profile.ServiceCredential != nil {
		copy := *profile.ServiceCredential
		profile.ServiceCredential = &copy
	}
	return profile
}
