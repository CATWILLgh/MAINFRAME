package main

import (
	"encoding/json"
	"fmt"
	"io"
)

func runReleaseReviewCommand(
	input io.Reader,
	output, errorOutput io.Writer,
) int {
	request, err := decodeReleaseChange(input)
	if err != nil {
		fmt.Fprintf(
			errorOutput,
			"release review: invalid request: %v\n",
			err,
		)
		return 2
	}
	response, err := reviewReleaseChange(request)
	if err != nil {
		fmt.Fprintf(errorOutput, "release review: %v\n", err)
		return 1
	}
	if err := json.NewEncoder(output).Encode(response); err != nil {
		fmt.Fprintf(errorOutput, "release review: encode response: %v\n", err)
		return 1
	}
	return 0
}

func runReleaseApplyCommand(
	confirmation string,
	input io.Reader,
	output, errorOutput io.Writer,
) int {
	if !releaseConfirmationPattern.MatchString(confirmation) {
		fmt.Fprintln(
			errorOutput,
			"release apply: confirmation digest is invalid",
		)
		return 2
	}
	request, err := decodeReleaseApply(input)
	if err != nil {
		fmt.Fprintf(
			errorOutput,
			"release apply: invalid request: %v\n",
			err,
		)
		return 2
	}
	response, err := applyReleaseChange(request, confirmation)
	if err != nil {
		fmt.Fprintf(errorOutput, "release apply: %v\n", err)
		return 1
	}
	if err := json.NewEncoder(output).Encode(response); err != nil {
		fmt.Fprintf(errorOutput, "release apply: encode response: %v\n", err)
		return 1
	}
	return 0
}

func runReleaseReviewFromRegistry(
	context commandContext,
	_ map[string]string,
) int {
	return runReleaseReviewCommand(
		context.input,
		context.output,
		context.errorOutput,
	)
}

func runReleaseApplyFromRegistry(
	context commandContext,
	captures map[string]string,
) int {
	return runReleaseApplyCommand(
		captures["digest"],
		context.input,
		context.output,
		context.errorOutput,
	)
}
