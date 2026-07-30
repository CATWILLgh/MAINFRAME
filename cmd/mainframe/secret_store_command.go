package main

import (
	"io"

	"github.com/CATWILLgh/MAINFRAME/internal/secretcli"
)

func runSecretStoreCommand(
	args []string,
	input io.Reader,
	output, errorOutput io.Writer,
) int {
	return secretcli.Run(args, input, output, errorOutput)
}
