package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"regexp"
)

var draftConfirmationPattern = regexp.MustCompile(
	`^sha256:[0-9a-f]{64}$`,
)

type draftApplyRunner func(
	draftReviewRequest,
	string,
) (draftApplyResponse, error)

func runDraftApplyFromRegistry(
	context commandContext,
	captures map[string]string,
) int {
	confirmation := captures["digest"]
	if !draftConfirmationPattern.MatchString(confirmation) {
		fmt.Fprintln(
			context.errorOutput,
			"draft apply: confirmation digest is invalid",
		)
		return 2
	}
	request, err := decodeDraftReviewRequest(context.input)
	if err != nil {
		fmt.Fprintln(context.errorOutput, "draft apply: request is invalid")
		return 2
	}
	if context.applyDraft == nil {
		fmt.Fprintln(context.errorOutput, "draft apply: applier is unavailable")
		return 1
	}
	response, err := context.applyDraft(request, confirmation)
	if err != nil {
		fmt.Fprintln(
			context.errorOutput,
			"draft apply: desired state could not be applied",
		)
		return 1
	}
	var encoded bytes.Buffer
	if err := json.NewEncoder(&encoded).Encode(response); err != nil {
		fmt.Fprintln(context.errorOutput, "draft apply: encode response failed")
		return 1
	}
	if _, err := context.output.Write(encoded.Bytes()); err != nil {
		fmt.Fprintln(context.errorOutput, "draft apply: write response failed")
		return 1
	}
	return 0
}
