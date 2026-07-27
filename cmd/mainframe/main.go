package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
)

const maxPlanRequestBytes = 1 << 20

type previewLauncher func(io.Reader, io.Writer) error

type planResponse struct {
	Operations []planOperation `json:"operations"`
}

type planOperation struct {
	ComponentID domain.ComponentID   `json:"component_id"`
	Kind        domain.OperationKind `json:"kind"`
	Artifact    planArtifact         `json:"artifact"`
	SourcePath  domain.ArtifactPath  `json:"source_path,omitempty"`
}

type planArtifact struct {
	Location  domain.Location        `json:"location"`
	Ownership domain.OwnershipStatus `json:"ownership,omitempty"`
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}

func run(args []string, input io.Reader, output, errorOutput io.Writer) int {
	return runWithPreview(args, input, output, errorOutput, runInteractivePreview)
}

func runWithPreview(
	args []string,
	input io.Reader,
	output, errorOutput io.Writer,
	launchPreview previewLauncher,
) int {
	if len(args) == 0 {
		if err := launchPreview(input, output); err != nil {
			fmt.Fprintf(errorOutput, "preview: %v\n", err)
			return 1
		}
		return 0
	}
	if args[0] == "credentials" {
		return runCredentialsCommand(
			args[1:],
			input,
			output,
			errorOutput,
		)
	}
	if len(args) != 1 || args[0] != "plan" {
		fmt.Fprintf(
			errorOutput,
			"unknown command %q; expected credentials, plan, or no arguments\n",
			args[0],
		)
		return 2
	}
	if err := runPlan(input, output); err != nil {
		fmt.Fprintf(errorOutput, "plan: %v\n", err)
		return 1
	}
	return 0
}

func runPlan(input io.Reader, output io.Writer) error {
	request, err := decodeRequest(input)
	if err != nil {
		return err
	}
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return err
	}
	result, err := plan.New(snapshot.release.Model.Catalog()).Plan(request)
	if err != nil {
		return err
	}
	if err := json.NewEncoder(output).Encode(publicPlanResponse(result)); err != nil {
		return fmt.Errorf("encode response: %w", err)
	}
	return nil
}

func publicPlanResponse(source domain.Plan) planResponse {
	operations := make([]planOperation, len(source.Operations))
	for index, operation := range source.Operations {
		operations[index] = planOperation{
			ComponentID: operation.ComponentID,
			Kind:        operation.Kind,
			Artifact: planArtifact{
				Location: operation.Artifact.Location, Ownership: operation.Artifact.Ownership,
			},
			SourcePath: operation.SourcePath,
		}
	}
	return planResponse{Operations: operations}
}

func decodeRequest(input io.Reader) (domain.PlanRequest, error) {
	return decodeStrictJSON[domain.PlanRequest](input)
}
