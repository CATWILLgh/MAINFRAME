package main

import (
	"encoding/json"
	"fmt"
	"io"
	"regexp"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
)

var credentialConfirmationPattern = regexp.MustCompile(
	`^sha256:[0-9a-f]{64}$`,
)

func runCredentialUsesCommand(
	name string,
	output, errorOutput io.Writer,
) int {
	reference := credentialcatalog.SecretReference{
		Backend: credentialcatalog.BackendSecretEnvironment,
		Name:    name,
	}
	if credentialcatalog.ValidateSecretReference(reference) != nil {
		fmt.Fprintln(
			errorOutput,
			"credentials uses: secret reference is invalid",
		)
		return 2
	}
	if err := runCredentialUses(reference, output); err != nil {
		fmt.Fprintf(errorOutput, "credentials uses: %v\n", err)
		return 1
	}
	return 0
}

func runCredentialReviewCommand(
	input io.Reader,
	output, errorOutput io.Writer,
) int {
	request, err := decodeCredentialInstanceChange(input)
	if err != nil {
		fmt.Fprintf(
			errorOutput,
			"credentials instance review: invalid request: %v\n",
			err,
		)
		return 2
	}
	response, err := reviewCredentialInstanceChange(request)
	if err != nil {
		fmt.Fprintf(
			errorOutput,
			"credentials instance review: %v\n",
			err,
		)
		return 1
	}
	if err := encodeCredentialResponse(output, response); err != nil {
		fmt.Fprintf(errorOutput, "credentials instance review: %v\n", err)
		return 1
	}
	return 0
}

func runCredentialApplyCommand(
	confirmation string,
	input io.Reader,
	output, errorOutput io.Writer,
) int {
	if !credentialConfirmationPattern.MatchString(confirmation) {
		fmt.Fprintln(
			errorOutput,
			"credentials instance apply: confirmation digest is invalid",
		)
		return 2
	}
	request, err := decodeCredentialApplyRequest(input)
	if err != nil {
		fmt.Fprintf(
			errorOutput,
			"credentials instance apply: invalid request: %v\n",
			err,
		)
		return 2
	}
	response, err := applyCredentialInstanceChange(request, confirmation)
	if err != nil {
		fmt.Fprintf(errorOutput, "credentials instance apply: %v\n", err)
		return 1
	}
	if err := encodeCredentialResponse(output, response); err != nil {
		fmt.Fprintf(errorOutput, "credentials instance apply: %v\n", err)
		return 1
	}
	return 0
}

func reviewCredentialInstanceChange(
	request credentialInstanceChangeRequest,
) (credentialInstanceReviewResponse, error) {
	session, err := buildCredentialMachineSession()
	if err != nil {
		return credentialInstanceReviewResponse{}, err
	}
	instance := internalCredentialInstance(request.Instance)
	desired, expected, err := editCredentialInstances(
		session,
		request,
		instance,
	)
	if err != nil {
		return credentialInstanceReviewResponse{}, err
	}
	reviewed, err := session.service.Review(application.Request{
		CredentialInstances: &desired,
	})
	if err != nil {
		return credentialInstanceReviewResponse{}, err
	}
	if !reviewed.CredentialOnlyApplicable() {
		return credentialInstanceReviewResponse{}, fmt.Errorf(
			"requested credential change is not applicable",
		)
	}
	if err := requireExactCredentialChange(
		reviewed.CredentialChanges(),
		expected,
	); err != nil {
		return credentialInstanceReviewResponse{}, err
	}
	commitment, err := credentialReviewCommitment(
		reviewed.Executable(),
		desired,
		session.scope,
	)
	if err != nil {
		return credentialInstanceReviewResponse{}, err
	}
	return credentialInstanceReviewResponse{
		SchemaVersion: credentialInstanceProtocolVersion,
		Kind:          credentialInstanceReviewKind,
		Operation:     request.Operation,
		Changes: []credentialChangeResponse{
			publicCredentialChange(expected),
		},
		ApplyRequest: credentialApplyRequest{
			SchemaVersion: credentialInstanceProtocolVersion,
			Kind:          credentialInstanceApplyKind,
			Operation:     request.Operation,
			InstanceID:    request.Instance.ID,
			Instances:     publicCredentialInstances(desired.All()),
		},
		ExpectedReview: commitment,
	}, nil
}

func editCredentialInstances(
	session credentialMachineSession,
	request credentialInstanceChangeRequest,
	instance credentialcatalog.Instance,
) (
	credentialcatalog.Instances,
	credentialcatalog.InstanceChange,
	error,
) {
	var desired credentialcatalog.Instances
	var err error
	if request.Operation == credentialOperationCreate {
		desired, _, err = credentialcatalog.CreateInstance(
			session.current,
			instance,
			session.definitions,
		)
	} else {
		desired, _, err = credentialcatalog.EditInstance(
			session.current,
			credentialcatalog.InstanceID(request.InstanceID),
			instance,
			session.definitions,
		)
	}
	if err != nil {
		return credentialcatalog.Instances{},
			credentialcatalog.InstanceChange{},
			err
	}
	changes, err := credentialcatalog.PlanInstanceChanges(
		session.current,
		desired,
	)
	if err != nil || len(changes) != 1 {
		if err == nil {
			err = fmt.Errorf("requested edit did not produce one credential change")
		}
		return credentialcatalog.Instances{},
			credentialcatalog.InstanceChange{},
			err
	}
	return desired, changes[0], nil
}

func applyCredentialInstanceChange(
	request credentialApplyRequest,
	confirmation string,
) (credentialApplyResponse, error) {
	session, err := buildCredentialMachineSession()
	if err != nil {
		return credentialApplyResponse{}, err
	}
	desired, err := buildDesiredCredentialInstances(
		request.Instances,
		session.definitions,
	)
	if err != nil {
		return credentialApplyResponse{}, err
	}
	reviewed, err := session.service.Review(application.Request{
		CredentialInstances: &desired,
	})
	if err != nil {
		return credentialApplyResponse{}, err
	}
	if !reviewed.CredentialOnlyApplicable() {
		return credentialApplyResponse{}, fmt.Errorf(
			"reviewed credential change is no longer applicable",
		)
	}
	if err := requireSingleCredentialChange(
		reviewed.CredentialChanges(),
		request.Operation,
		credentialcatalog.InstanceID(request.InstanceID),
	); err != nil {
		return credentialApplyResponse{}, err
	}
	currentCommitment, err := credentialReviewCommitment(
		reviewed.Executable(),
		desired,
		session.scope,
	)
	if err != nil {
		return credentialApplyResponse{}, err
	}
	if !credentialCommitmentsEqual(currentCommitment, confirmation) {
		return credentialApplyResponse{}, fmt.Errorf(
			"review confirmation is stale; run review again",
		)
	}
	result, err := session.service.ApplyCredentials(reviewed)
	if err != nil {
		return credentialApplyResponse{}, err
	}
	return credentialApplyResponse{
		SchemaVersion: credentialInstanceProtocolVersion,
		Kind:          credentialApplyResultKind,
		Applied:       true,
		Warnings:      append([]string{}, result.Warnings...),
	}, nil
}

func buildDesiredCredentialInstances(
	instances []credentialInstance,
	definitions credentialcatalog.Definitions,
) (credentialcatalog.Instances, error) {
	internal := make([]credentialcatalog.Instance, len(instances))
	for index, instance := range instances {
		internal[index] = internalCredentialInstance(instance)
	}
	return credentialcatalog.BuildInstances(internal, definitions)
}

func encodeCredentialResponse(output io.Writer, response any) error {
	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(response); err != nil {
		return fmt.Errorf("encode response: %w", err)
	}
	return nil
}
