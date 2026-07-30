package main

import (
	"errors"
	"fmt"
	"io"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
)

const (
	credentialInstanceProtocolVersion = 1
	credentialInstanceChangeKind      = "mainframe-credential-instance-change"
	credentialOperationCreate         = "create"
	credentialOperationEdit           = "edit"
	credentialOperationDelete         = "delete"
	credentialCommitmentKind          = "mainframe-credential-review-commitment"
	credentialInstanceReviewKind      = "mainframe-credential-instance-review"
	credentialInstanceApplyKind       = "mainframe-credential-instances-apply"
	credentialApplyResultKind         = "mainframe-credential-instance-apply-result"
)

type credentialInstanceChangeRequest struct {
	SchemaVersion int                 `json:"schema_version"`
	Kind          string              `json:"kind"`
	Operation     string              `json:"operation"`
	InstanceID    string              `json:"instance_id,omitempty"`
	Instance      *credentialInstance `json:"instance,omitempty"`
}

type credentialApplyRequest struct {
	SchemaVersion int                  `json:"schema_version"`
	Kind          string               `json:"kind"`
	Operation     string               `json:"operation"`
	InstanceID    string               `json:"instance_id"`
	Instances     []credentialInstance `json:"instances"`
}

type credentialInstanceReviewResponse struct {
	SchemaVersion  int                        `json:"schema_version"`
	Kind           string                     `json:"kind"`
	Operation      string                     `json:"operation"`
	Changes        []credentialChangeResponse `json:"changes"`
	ApplyRequest   credentialApplyRequest     `json:"apply_request"`
	ExpectedReview string                     `json:"expected_review"`
}

type credentialChangeResponse struct {
	Operation string              `json:"operation"`
	Before    *credentialInstance `json:"before,omitempty"`
	After     *credentialInstance `json:"after,omitempty"`
}

type credentialApplyResponse struct {
	SchemaVersion int      `json:"schema_version"`
	Kind          string   `json:"kind"`
	Applied       bool     `json:"applied"`
	Warnings      []string `json:"warnings"`
}

func decodeCredentialInstanceChange(
	input io.Reader,
) (credentialInstanceChangeRequest, error) {
	request, err := decodeStrictJSON[credentialInstanceChangeRequest](input)
	if err != nil {
		return credentialInstanceChangeRequest{}, err
	}
	if request.SchemaVersion != credentialInstanceProtocolVersion {
		return credentialInstanceChangeRequest{}, fmt.Errorf(
			"unsupported schema version %d",
			request.SchemaVersion,
		)
	}
	if request.Kind != credentialInstanceChangeKind {
		return credentialInstanceChangeRequest{}, errors.New(
			"request kind is unsupported",
		)
	}
	switch request.Operation {
	case credentialOperationCreate:
		if request.InstanceID != "" || request.Instance == nil {
			return credentialInstanceChangeRequest{}, errors.New(
				"create request must include instance and not instance_id",
			)
		}
	case credentialOperationEdit:
		if request.Instance == nil ||
			request.InstanceID == "" ||
			request.InstanceID != request.Instance.ID {
			return credentialInstanceChangeRequest{}, errors.New(
				"edit request instance_id must match instance.id",
			)
		}
	case credentialOperationDelete:
		if request.InstanceID == "" || request.Instance != nil {
			return credentialInstanceChangeRequest{}, errors.New(
				"delete request must include instance_id and not instance",
			)
		}
	default:
		return credentialInstanceChangeRequest{}, errors.New(
			"credential operation is unsupported",
		)
	}
	return request, nil
}

func decodeCredentialApplyRequest(input io.Reader) (credentialApplyRequest, error) {
	request, err := decodeStrictJSON[credentialApplyRequest](input)
	if err != nil {
		return credentialApplyRequest{}, err
	}
	if request.SchemaVersion != credentialInstanceProtocolVersion {
		return credentialApplyRequest{}, fmt.Errorf(
			"unsupported schema version %d",
			request.SchemaVersion,
		)
	}
	if request.Kind != credentialInstanceApplyKind {
		return credentialApplyRequest{}, errors.New(
			"request kind is unsupported",
		)
	}
	if request.Instances == nil {
		return credentialApplyRequest{}, errors.New(
			"apply request instances must be an array",
		)
	}
	if request.InstanceID == "" ||
		request.Operation != credentialOperationCreate &&
			request.Operation != credentialOperationEdit &&
			request.Operation != credentialOperationDelete {
		return credentialApplyRequest{}, errors.New(
			"apply request operation or instance_id is invalid",
		)
	}
	return request, nil
}

func requireExactCredentialChange(
	reviewed []credentialcatalog.InstanceChange,
	expected credentialcatalog.InstanceChange,
) error {
	if len(reviewed) != 1 ||
		!reflect.DeepEqual(
			publicCredentialChange(reviewed[0]),
			publicCredentialChange(expected),
		) {
		return errors.New(
			"credential state changed while the requested change was reviewed",
		)
	}
	return nil
}

func requireSingleCredentialChange(
	reviewed []credentialcatalog.InstanceChange,
	operation string,
	instanceID credentialcatalog.InstanceID,
) error {
	if len(reviewed) != 1 ||
		changeInstanceID(reviewed[0]) != instanceID {
		return errors.New(
			"apply request does not describe exactly one reviewed instance change",
		)
	}
	expectedKind := credentialcatalog.ChangeCreate
	if operation == credentialOperationEdit {
		expectedKind = credentialcatalog.ChangeUpdate
	} else if operation == credentialOperationDelete {
		expectedKind = credentialcatalog.ChangeDelete
	}
	if reviewed[0].Kind != expectedKind {
		return errors.New(
			"apply operation differs from the reviewed instance change",
		)
	}
	return nil
}

func changeInstanceID(
	change credentialcatalog.InstanceChange,
) credentialcatalog.InstanceID {
	if change.Kind == credentialcatalog.ChangeDelete {
		return change.Before.ID
	}
	return change.After.ID
}

func internalCredentialInstance(
	instance credentialInstance,
) credentialcatalog.Instance {
	credentials := make(
		[]credentialcatalog.CredentialBinding,
		len(instance.Credentials),
	)
	for index, binding := range instance.Credentials {
		requirements := make(
			[]credentialcatalog.Requirement,
			len(binding.Requirements),
		)
		for requirementIndex, requirement := range binding.Requirements {
			requirements[requirementIndex] = credentialcatalog.Requirement{
				Action: credentialcatalog.RequirementAction(requirement.Action),
				InstanceID: credentialcatalog.InstanceID(
					requirement.InstanceID,
				),
				RoleID:  credentialcatalog.RoleID(requirement.RoleID),
				Summary: requirement.Summary,
			}
		}
		credentials[index] = credentialcatalog.CredentialBinding{
			RoleID: credentialcatalog.RoleID(binding.RoleID),
			Secret: credentialcatalog.SecretReference{
				Backend: credentialcatalog.SecretBackend(binding.Secret.Backend),
				Name:    binding.Secret.Name,
			},
			Requirements: requirements,
		}
	}
	return credentialcatalog.Instance{
		ID: credentialcatalog.InstanceID(instance.ID),
		ServiceID: credentialcatalog.ServiceID(
			instance.ServiceID,
		),
		Name: instance.Name, Purpose: instance.Purpose,
		Locator: instance.Locator, Credentials: credentials,
	}
}

func publicCredentialChange(
	change credentialcatalog.InstanceChange,
) credentialChangeResponse {
	operation := credentialOperationCreate
	if change.Kind == credentialcatalog.ChangeUpdate {
		operation = credentialOperationEdit
	} else if change.Kind == credentialcatalog.ChangeDelete {
		operation = credentialOperationDelete
	}
	response := credentialChangeResponse{
		Operation: operation,
	}
	if change.Kind != credentialcatalog.ChangeDelete {
		after := publicCredentialInstances(
			[]credentialcatalog.Instance{change.After},
		)[0]
		response.After = &after
	}
	if change.Kind != credentialcatalog.ChangeCreate {
		before := publicCredentialInstances(
			[]credentialcatalog.Instance{change.Before},
		)[0]
		response.Before = &before
	}
	return response
}
