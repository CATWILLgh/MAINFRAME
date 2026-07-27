package main

import (
	"embed"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
)

//go:embed docs/*.md
var embeddedDocumentation embed.FS

type documentationTopic struct {
	ID         string
	Title      string
	Summary    string
	File       string
	CommandIDs []string
}

type capabilitiesResponse struct {
	SchemaVersion int                       `json:"schema_version"`
	Kind          string                    `json:"kind"`
	Invocation    string                    `json:"invocation"`
	Help          []string                  `json:"help"`
	Commands      []commandCapability       `json:"commands"`
	Documentation []documentationCapability `json:"documentation"`
}

type commandCapability struct {
	ID            string              `json:"id"`
	Usage         string              `json:"usage"`
	Summary       string              `json:"summary"`
	Input         commandInput        `json:"input"`
	Output        commandOutput       `json:"output"`
	Effect        commandEffect       `json:"effect"`
	Confirmation  commandConfirmation `json:"confirmation"`
	Documentation string              `json:"documentation"`
}

type documentationCapability struct {
	ID      string `json:"id"`
	Title   string `json:"title"`
	Summary string `json:"summary"`
	Command string `json:"command"`
}

func documentationRegistry() []documentationTopic {
	return []documentationTopic{
		{
			ID:      "overview",
			Title:   "Overview",
			Summary: "How MAINFRAME separates choices, preview, confirmation, and application.",
			File:    "docs/overview.md",
			CommandIDs: []string{
				"tui.open", "docs.list", "docs.show",
			},
		},
		{
			ID:      "adapters-and-mcp",
			Title:   "Adapters and MCP",
			Summary: "Adapter isolation and MCP connection management.",
			File:    "docs/adapters-and-mcp.md",
			CommandIDs: []string{
				"tui.open",
			},
		},
		{
			ID:      "credentials",
			Title:   "Credentials",
			Summary: "Service instances, shared secret references, and safe value entry.",
			File:    "docs/credentials.md",
			CommandIDs: []string{
				"credentials.catalog",
				"credentials.uses",
				"credentials.instance.review",
				"credentials.instance.apply",
			},
		},
		{
			ID:      "agent-automation",
			Title:   "Agent automation",
			Summary: "Machine-readable interfaces for discovery, review, and exact application.",
			File:    "docs/agent-automation.md",
			CommandIDs: []string{
				"capabilities",
				"plan",
				"draft.review",
				"credentials.catalog",
				"credentials.uses",
				"credentials.instance.review",
				"credentials.instance.apply",
			},
		},
	}
}

func runDocsListCommand(context commandContext, _ map[string]string) int {
	if err := validateCommandAndDocumentationRegistry(); err != nil {
		fmt.Fprintf(context.errorOutput, "docs list: %v\n", err)
		return 1
	}
	fmt.Fprintln(context.output, "Documentation included with this MAINFRAME executable:")
	for _, topic := range sortedDocumentationTopics() {
		fmt.Fprintf(
			context.output,
			"  %-20s %s\n",
			topic.ID,
			topic.Summary,
		)
	}
	return 0
}

func runDocsShowCommand(
	context commandContext,
	captures map[string]string,
) int {
	topic, exists := documentationTopicByID(captures["topic"])
	if !exists {
		fmt.Fprintln(context.errorOutput, "docs show: unknown documentation topic")
		return 2
	}
	content, err := embeddedDocumentation.ReadFile(topic.File)
	if err != nil {
		fmt.Fprintf(context.errorOutput, "docs show: read embedded topic: %v\n", err)
		return 1
	}
	if _, err := context.output.Write(content); err != nil {
		fmt.Fprintf(context.errorOutput, "docs show: write topic: %v\n", err)
		return 1
	}
	return 0
}

func runCapabilitiesCommand(
	context commandContext,
	_ map[string]string,
) int {
	if err := validateCommandAndDocumentationRegistry(); err != nil {
		fmt.Fprintf(context.errorOutput, "capabilities: %v\n", err)
		return 1
	}
	response := publicCapabilities()
	if err := json.NewEncoder(context.output).Encode(response); err != nil {
		fmt.Fprintf(context.errorOutput, "capabilities: encode response: %v\n", err)
		return 1
	}
	return 0
}

func publicCapabilities() capabilitiesResponse {
	commands := commandRegistry()
	sort.Slice(commands, func(i, j int) bool {
		return commands[i].ID < commands[j].ID
	})
	publicCommands := make([]commandCapability, len(commands))
	for index, command := range commands {
		publicCommands[index] = commandCapability{
			ID: command.ID, Usage: command.Usage, Summary: command.Summary,
			Input: command.Input, Output: command.Output, Effect: command.Effect,
			Confirmation:  command.Confirmation,
			Documentation: command.Documentation,
		}
	}
	topics := sortedDocumentationTopics()
	publicTopics := make([]documentationCapability, len(topics))
	for index, topic := range topics {
		publicTopics[index] = documentationCapability{
			ID: topic.ID, Title: topic.Title, Summary: topic.Summary,
			Command: "mainframe docs show " + topic.ID,
		}
	}
	return capabilitiesResponse{
		SchemaVersion: 1,
		Kind:          "mainframe-capabilities",
		Invocation:    "mainframe",
		Help: []string{
			"mainframe --help",
			"mainframe help [command ...]",
			"mainframe <command> --help",
		},
		Commands:      publicCommands,
		Documentation: publicTopics,
	}
}

func validateCommandAndDocumentationRegistry() error {
	commands := commandRegistry()
	topics := documentationRegistry()
	commandIDs, err := validateCommandEntries(commands)
	if err != nil {
		return err
	}
	topicCommands, err := validateDocumentationEntries(topics, commandIDs)
	if err != nil {
		return err
	}
	for _, command := range commands {
		documented, exists := topicCommands[command.Documentation]
		if !exists {
			return fmt.Errorf(
				"command %q references unknown documentation topic %q",
				command.ID,
				command.Documentation,
			)
		}
		if !documented[command.ID] {
			return fmt.Errorf(
				"documentation topic %q does not reference command %q",
				command.Documentation,
				command.ID,
			)
		}
	}
	return nil
}

func validateCommandEntries(commands []commandSpec) (map[string]bool, error) {
	commandIDs := make(map[string]bool, len(commands))
	patterns := make(map[string]bool, len(commands))
	for _, command := range commands {
		if command.ID == "" ||
			command.Usage == "" ||
			command.Summary == "" ||
			command.Input == "" ||
			command.Output == "" ||
			command.Effect == "" ||
			command.Confirmation == "" ||
			command.Documentation == "" ||
			command.Handler == nil {
			return nil, fmt.Errorf("command registry contains an incomplete entry")
		}
		if commandIDs[command.ID] {
			return nil, fmt.Errorf("duplicate command id %q", command.ID)
		}
		commandIDs[command.ID] = true
		pattern := normalizedCommandPattern(command.Pattern)
		if patterns[pattern] {
			return nil, fmt.Errorf("duplicate command pattern %q", pattern)
		}
		patterns[pattern] = true
	}
	return commandIDs, nil
}

func validateDocumentationEntries(
	topics []documentationTopic,
	commandIDs map[string]bool,
) (map[string]map[string]bool, error) {
	topicCommands := make(map[string]map[string]bool, len(topics))
	for _, topic := range topics {
		if topic.ID == "" ||
			topic.Title == "" ||
			topic.Summary == "" ||
			topic.File == "" ||
			len(topic.CommandIDs) == 0 {
			return nil, fmt.Errorf("documentation registry contains an incomplete entry")
		}
		if _, exists := topicCommands[topic.ID]; exists {
			return nil, fmt.Errorf("duplicate documentation topic %q", topic.ID)
		}
		content, err := embeddedDocumentation.ReadFile(topic.File)
		if err != nil {
			return nil, fmt.Errorf("read documentation topic %q: %w", topic.ID, err)
		}
		if len(content) == 0 {
			return nil, fmt.Errorf("documentation topic %q is empty", topic.ID)
		}
		documented := make(map[string]bool, len(topic.CommandIDs))
		for _, commandID := range topic.CommandIDs {
			if !commandIDs[commandID] {
				return nil, fmt.Errorf(
					"documentation topic %q references unknown command %q",
					topic.ID,
					commandID,
				)
			}
			if documented[commandID] {
				return nil, fmt.Errorf(
					"documentation topic %q repeats command %q",
					topic.ID,
					commandID,
				)
			}
			documented[commandID] = true
		}
		topicCommands[topic.ID] = documented
	}
	return topicCommands, nil
}

func normalizedCommandPattern(pattern []string) string {
	normalized := make([]string, len(pattern))
	for index, segment := range pattern {
		if _, placeholder := placeholderName(segment); placeholder {
			normalized[index] = "<>"
		} else {
			normalized[index] = segment
		}
	}
	return strings.Join(normalized, "\x00")
}

func sortedDocumentationTopics() []documentationTopic {
	topics := documentationRegistry()
	sort.Slice(topics, func(i, j int) bool {
		return topics[i].ID < topics[j].ID
	})
	return topics
}

func documentationTopicByID(id string) (documentationTopic, bool) {
	for _, topic := range documentationRegistry() {
		if topic.ID == id {
			return topic, true
		}
	}
	return documentationTopic{}, false
}
