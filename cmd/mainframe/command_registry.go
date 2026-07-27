package main

import (
	"fmt"
	"io"
	"sort"
)

type commandContext struct {
	input         io.Reader
	output        io.Writer
	errorOutput   io.Writer
	launchPreview previewLauncher
	reviewDraft   draftReviewRunner
}

type commandHandler func(commandContext, map[string]string) int

type commandHandlerKind string
type commandInput string
type commandOutput string
type commandEffect string
type commandConfirmation string

const (
	handlerTUI              commandHandlerKind = "tui"
	handlerPlan             commandHandlerKind = "plan"
	handlerDraftReview      commandHandlerKind = "draft-review"
	handlerCredentialList   commandHandlerKind = "credential-list"
	handlerCredentialUses   commandHandlerKind = "credential-uses"
	handlerCredentialReview commandHandlerKind = "credential-review"
	handlerCredentialApply  commandHandlerKind = "credential-apply"
	handlerDocsList         commandHandlerKind = "docs-list"
	handlerDocsShow         commandHandlerKind = "docs-show"
	handlerCapabilities     commandHandlerKind = "capabilities"
)

const (
	inputNone      commandInput = "none"
	inputArguments commandInput = "arguments"
	inputJSON      commandInput = "json-stdin"
	inputTerminal  commandInput = "terminal"
)

const (
	outputJSON     commandOutput = "json-stdout"
	outputTerminal commandOutput = "terminal"
	outputText     commandOutput = "text-stdout"
)

const (
	effectReadOnly      commandEffect = "read-only"
	effectReviewedWrite commandEffect = "reviewed-write"
)

const (
	confirmationNone     commandConfirmation = "none"
	confirmationDigest   commandConfirmation = "digest"
	confirmationTerminal commandConfirmation = "in-terminal"
)

type commandSpec struct {
	ID            string
	Pattern       []string
	Usage         string
	Summary       string
	Input         commandInput
	Output        commandOutput
	Effect        commandEffect
	Confirmation  commandConfirmation
	Documentation string
	HandlerKind   commandHandlerKind
	Handler       commandHandler
}

func commandRegistry() []commandSpec {
	commands := append([]commandSpec(nil), registeredCommands...)
	for index := range commands {
		commands[index].Handler = commandHandlerForKind(commands[index].HandlerKind)
	}
	return commands
}

func commandHandlerForKind(kind commandHandlerKind) commandHandler {
	switch kind {
	case handlerTUI:
		return runTUICommand
	case handlerPlan:
		return runPlanCommand
	case handlerDraftReview:
		return runDraftReviewFromRegistry
	case handlerCredentialList:
		return runCredentialCatalogCommand
	case handlerCredentialUses:
		return runCredentialUsesFromRegistry
	case handlerCredentialReview:
		return runCredentialReviewFromRegistry
	case handlerCredentialApply:
		return runCredentialApplyFromRegistry
	case handlerDocsList:
		return runDocsListCommand
	case handlerDocsShow:
		return runDocsShowCommand
	case handlerCapabilities:
		return runCapabilitiesCommand
	default:
		return nil
	}
}

func dispatchRegisteredCommand(args []string, context commandContext) (int, bool) {
	for _, command := range commandRegistry() {
		captures, matches := matchCommandPattern(command.Pattern, args)
		if matches {
			return command.Handler(context, captures), true
		}
	}
	return 0, false
}

func matchCommandPattern(pattern, args []string) (map[string]string, bool) {
	if len(pattern) != len(args) {
		return nil, false
	}
	captures := make(map[string]string)
	for index, segment := range pattern {
		name, placeholder := placeholderName(segment)
		if placeholder {
			if args[index] == "" {
				return nil, false
			}
			captures[name] = args[index]
			continue
		}
		if segment != args[index] {
			return nil, false
		}
	}
	return captures, true
}

func placeholderName(segment string) (string, bool) {
	if len(segment) < 3 ||
		segment[0] != '<' ||
		segment[len(segment)-1] != '>' {
		return "", false
	}
	return segment[1 : len(segment)-1], true
}

func helpPath(args []string) ([]string, bool) {
	if len(args) == 0 {
		return nil, false
	}
	if args[0] == "help" {
		return args[1:], true
	}
	last := args[len(args)-1]
	if last == "--help" || last == "-h" {
		return args[:len(args)-1], true
	}
	return nil, false
}

func renderCommandHelp(path []string, output io.Writer) error {
	commands := matchingHelpCommands(path)
	if len(commands) == 0 {
		return fmt.Errorf("unknown help topic")
	}
	if len(path) == 0 {
		fmt.Fprintln(output, "MAINFRAME manages installation, updates, adapters, MCP connections, and local diagnostics.")
		fmt.Fprintln(output)
		fmt.Fprintln(output, "In the terminal interface, installation and configuration choices are written only after a final preview and confirmation.")
		fmt.Fprintln(output, "Secret values use a separate masked entry and explicit confirmation.")
		fmt.Fprintln(output)
	}
	fmt.Fprintln(output, "Usage:")
	for _, command := range commands {
		fmt.Fprintf(output, "  %-62s %s\n", command.Usage, command.Summary)
	}
	if len(path) == 0 {
		fmt.Fprintln(output)
		fmt.Fprintln(output, "Help:")
		fmt.Fprintln(output, "  mainframe help [command ...]")
		fmt.Fprintln(output, "  mainframe <command> --help")
		fmt.Fprintln(output)
		fmt.Fprintln(output, "Run `mainframe docs list` for the documentation included with this executable.")
		fmt.Fprintln(output, "Run `mainframe capabilities --json` for the machine-readable contract.")
	}
	return nil
}

func matchingHelpCommands(path []string) []commandSpec {
	commands := make([]commandSpec, 0)
	for _, command := range commandRegistry() {
		if commandPatternHasPrefix(command.Pattern, path) {
			commands = append(commands, command)
		}
	}
	sort.Slice(commands, func(i, j int) bool {
		return commands[i].Usage < commands[j].Usage
	})
	return commands
}

func commandPatternHasPrefix(pattern, prefix []string) bool {
	if len(prefix) > len(pattern) {
		return false
	}
	for index, segment := range prefix {
		if _, placeholder := placeholderName(pattern[index]); !placeholder &&
			pattern[index] != segment {
			return false
		}
	}
	return true
}

func runTUICommand(context commandContext, _ map[string]string) int {
	if err := context.launchPreview(context.input, context.output); err != nil {
		fmt.Fprintf(context.errorOutput, "preview: %v\n", err)
		return 1
	}
	return 0
}

func runPlanCommand(context commandContext, _ map[string]string) int {
	if err := runPlan(context.input, context.output); err != nil {
		fmt.Fprintf(context.errorOutput, "plan: %v\n", err)
		return 1
	}
	return 0
}

func runCredentialCatalogCommand(context commandContext, _ map[string]string) int {
	if err := runCredentials(context.output); err != nil {
		fmt.Fprintf(context.errorOutput, "credentials: %v\n", err)
		return 1
	}
	return 0
}

func runCredentialUsesFromRegistry(
	context commandContext,
	captures map[string]string,
) int {
	return runCredentialUsesCommand(
		captures["name"],
		context.output,
		context.errorOutput,
	)
}

func runCredentialReviewFromRegistry(
	context commandContext,
	_ map[string]string,
) int {
	return runCredentialReviewCommand(
		context.input,
		context.output,
		context.errorOutput,
	)
}

func runCredentialApplyFromRegistry(
	context commandContext,
	captures map[string]string,
) int {
	return runCredentialApplyCommand(
		captures["digest"],
		context.input,
		context.output,
		context.errorOutput,
	)
}
