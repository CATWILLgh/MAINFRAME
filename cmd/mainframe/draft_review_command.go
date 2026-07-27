package main

import (
	"bytes"
	"encoding/json"
	"fmt"
)

type draftReviewRunner func(draftReviewRequest) (draftReviewResponse, error)

func runDraftReviewFromRegistry(
	context commandContext,
	_ map[string]string,
) int {
	request, err := decodeDraftReviewRequest(context.input)
	if err != nil {
		fmt.Fprintf(context.errorOutput, "draft review: %v\n", err)
		return 1
	}
	if context.reviewDraft == nil {
		fmt.Fprintln(context.errorOutput, "draft review: reviewer is unavailable")
		return 1
	}
	response, err := context.reviewDraft(request)
	if err != nil {
		fmt.Fprintln(
			context.errorOutput,
			"draft review: desired state could not be reviewed",
		)
		return 1
	}
	var encoded bytes.Buffer
	if err := json.NewEncoder(&encoded).Encode(response); err != nil {
		fmt.Fprintf(context.errorOutput, "draft review: encode response: %v\n", err)
		return 1
	}
	if _, err := context.output.Write(encoded.Bytes()); err != nil {
		fmt.Fprintf(context.errorOutput, "draft review: write response: %v\n", err)
		return 1
	}
	return 0
}
