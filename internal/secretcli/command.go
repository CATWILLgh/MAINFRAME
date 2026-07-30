package secretcli

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/CATWILLgh/MAINFRAME/internal/secretstore"
)

func Run(args []string, input io.Reader, output, errorOutput io.Writer) int {
	if len(args) == 0 {
		args = []string{"help"}
	}
	store := secretstore.New(storeDirectory())
	var err error
	switch args[0] {
	case "set":
		if len(args) != 3 {
			return usage(errorOutput, "secret set NAME VALUE")
		}
		err = store.Set(args[1], args[2])
	case "create-stdin":
		if len(args) != 2 {
			return usage(errorOutput, "secret create-stdin NAME")
		}
		err = store.Create(args[1], input)
	case "get":
		if len(args) != 2 {
			return usage(errorOutput, "secret get NAME")
		}
		var value string
		value, err = store.Get(args[1])
		if err == nil {
			_, err = io.WriteString(output, value)
		}
	case "del":
		if len(args) != 2 {
			return usage(errorOutput, "secret del NAME")
		}
		err = store.Delete(args[1])
	case "list":
		if len(args) != 1 {
			return usage(errorOutput, "secret list")
		}
		var names []string
		names, err = store.List()
		if err == nil {
			for _, name := range names {
				fmt.Fprintln(output, name)
			}
		}
	case "edit":
		if len(args) != 1 {
			return usage(errorOutput, "secret edit")
		}
		err = store.Edit()
	case "prepare-retire":
		if len(args) != 2 {
			return usage(errorOutput, "secret prepare-retire NAME")
		}
		var generation string
		generation, err = store.PrepareRetire(args[1])
		if err == nil {
			fmt.Fprintln(output, generation)
		}
	case "del-if-generation":
		if len(args) != 3 {
			return usage(errorOutput, "secret del-if-generation NAME GENERATION")
		}
		err = store.DeleteIfGeneration(args[1], args[2])
	case "help", "-h", "--help":
		if len(args) != 1 {
			return usage(errorOutput, "secret help")
		}
		renderHelp(output)
		return 0
	default:
		fmt.Fprintf(errorOutput, "secret: unknown command %q — try 'secret help'\n", args[0])
		return 2
	}
	if err == nil {
		return 0
	}
	return reportError(args[0], err, errorOutput)
}

func storeDirectory() string {
	if root := os.Getenv("XDG_CONFIG_HOME"); root != "" {
		return filepath.Join(root, "credentials")
	}
	return filepath.Join(os.Getenv("HOME"), ".config", "credentials")
}

func usage(output io.Writer, message string) int {
	fmt.Fprintf(output, "Usage: %s\n", message)
	return 2
}

func reportError(command string, err error, output io.Writer) int {
	switch {
	case errors.Is(err, secretstore.ErrUnsafeStore):
		fmt.Fprintln(output, "secret: credential store is unsafe")
	case errors.Is(err, secretstore.ErrAlreadyExists):
		fmt.Fprintln(output, "secret: stdin secret cannot replace an existing entry")
	case command == "create-stdin" && errors.Is(err, secretstore.ErrInvalidInput):
		fmt.Fprintln(output, "secret: stdin value is invalid")
	case errors.Is(err, secretstore.ErrNotFound):
		fmt.Fprintln(output, "secret: no entry for the requested name")
	case errors.Is(err, secretstore.ErrGenerationChanged):
		fmt.Fprintln(output, "secret: store changed after retirement was prepared")
	case errors.Is(err, secretstore.ErrInvalidInput):
		fmt.Fprintln(output, "secret: name or value is invalid")
	default:
		fmt.Fprintln(output, "secret: operation failed safely")
	}
	return 1
}

func renderHelp(output io.Writer) {
	fmt.Fprintln(output, `secret — personal secrets manager (file-based, cross-platform)

Usage:
  secret set NAME VALUE       add or replace a secret
  secret create-stdin NAME    create a secret from standard input (no overwrite)
  secret get NAME             print a value (use inline: $(secret get NAME))
  secret del NAME             delete a secret
  secret list                 show all names (no values)
  secret edit                 open store in $EDITOR
  secret help                 this message

Storage:  ${XDG_CONFIG_HOME:-$HOME/.config}/credentials/secrets.env  (mode 0600)
Backup:   ${XDG_CONFIG_HOME:-$HOME/.config}/credentials/secrets.env.bak  (mode 0600)
For credential discovery, run `+"`mainframe credentials`"+` first.
Adapter-local credentials indexes are read-only migration fallbacks.`)
}
