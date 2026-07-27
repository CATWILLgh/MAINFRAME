package application

import (
	"errors"
	"fmt"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

type Request struct {
	Components          []domain.ComponentID
	MCPSelections       []mcpcatalog.Selection
	MCPCredentials      []MCPCredentialBinding
	Diagnostics         diagnostics.Desired
	CredentialInstances *credentialcatalog.Instances
}

type Snapshot struct {
	Release     executor.ReleaseIdentity
	Lifecycle   lifecycle.Service
	Credentials *credentialcatalog.InstanceSnapshot
}

type SnapshotBuilder interface {
	Build(Request) (Snapshot, error)
}

type ApplySession interface {
	Apply(executor.Preview) (executor.Result, error)
	ApplyWithoutRecovery(executor.Preview) (executor.Result, error)
	Close() error
}

type ApplyExecutorFactory interface {
	Open(executor.Refresher) (ApplySession, error)
}

type Service struct {
	snapshots SnapshotBuilder
	executors ApplyExecutorFactory
	recovery  RecoveryService
}

type ReviewedPlan struct {
	request                  Request
	semantic                 lifecycle.Preview
	executable               executor.Preview
	credentials              []credentialcatalog.InstanceChange
	applicable               bool
	credentialOnlyApplicable bool
	reviewed                 bool
}

func New(
	snapshots SnapshotBuilder,
	executors ApplyExecutorFactory,
	recoveryExecutors RecoveryExecutorFactory,
) (Service, error) {
	if snapshots == nil {
		return Service{}, errors.New("snapshot builder must not be nil")
	}
	if executors == nil {
		return Service{}, errors.New("apply executor factory must not be nil")
	}
	recovery, err := NewRecovery(recoveryExecutors)
	if err != nil {
		return Service{}, err
	}
	return Service{
		snapshots: snapshots,
		executors: executors,
		recovery:  recovery,
	}, nil
}

func (service Service) Review(request Request) (ReviewedPlan, error) {
	return Reviewer{snapshots: service.snapshots}.Review(request)
}

func (service Service) Recover() (executor.Result, error) {
	return service.recovery.Recover()
}

func (service Service) Apply(
	plan ReviewedPlan,
) (executor.Result, error) {
	if !plan.reviewed {
		return executor.Result{}, errors.New("plan was not produced by Review")
	}
	recovered, err := service.recovery.Recover()
	if err != nil {
		return recovered, fmt.Errorf("recover before apply: %w", err)
	}
	applied, err := service.applyReviewed(plan, false, false)
	applied.Warnings = append(recovered.Warnings, applied.Warnings...)
	return applied, err
}

func (service Service) ApplyCredentials(
	plan ReviewedPlan,
) (executor.Result, error) {
	if !plan.reviewed {
		return executor.Result{}, errors.New("plan was not produced by Review")
	}
	if !plan.credentialOnlyApplicable ||
		len(plan.executable.Plan.Operations) != 0 ||
		plan.request.CredentialInstances == nil ||
		credentialcatalog.ValidateInstancesOnlyPlan(
			plan.executable.Configuration,
			*plan.request.CredentialInstances,
		) != nil {
		return executor.Result{}, errors.New(
			"plan contains changes outside credential metadata",
		)
	}
	return service.applyReviewed(plan, true, false)
}

func (service Service) applyReviewed(
	plan ReviewedPlan,
	withoutRecovery bool,
	requireApplicable bool,
) (result executor.Result, err error) {
	request := cloneRequest(plan.request)
	refresher := requestRefresher{
		snapshots: service.snapshots, request: request,
		requireApplicable: requireApplicable,
	}
	session, err := service.executors.Open(refresher)
	if err != nil {
		return executor.Result{}, fmt.Errorf("open apply executor: %w", err)
	}
	if session == nil {
		return executor.Result{}, errors.New("open apply executor: factory returned nil")
	}
	defer func() {
		closeErr := session.Close()
		if closeErr == nil {
			return
		}
		wrapped := fmt.Errorf("close apply executor: %w", closeErr)
		if err != nil {
			err = errors.Join(err, wrapped)
			return
		}
		result.Warnings = append(result.Warnings, wrapped.Error())
	}()
	executable := cloneExecutable(plan.executable)
	if withoutRecovery {
		return session.ApplyWithoutRecovery(executable)
	}
	return session.Apply(executable)
}

func (plan ReviewedPlan) Request() Request {
	return cloneRequest(plan.request)
}

func (plan ReviewedPlan) Semantic() lifecycle.Preview {
	return cloneSemantic(plan.semantic)
}

func (plan ReviewedPlan) Executable() executor.Preview {
	return cloneExecutable(plan.executable)
}

func (plan ReviewedPlan) CredentialChanges() []credentialcatalog.InstanceChange {
	return cloneCredentialChanges(plan.credentials)
}

func (plan ReviewedPlan) CredentialOnlyApplicable() bool {
	return plan.credentialOnlyApplicable
}

func (plan ReviewedPlan) Applicable() bool {
	return plan.applicable
}

type requestRefresher struct {
	snapshots         SnapshotBuilder
	request           Request
	requireApplicable bool
}

func (refresher requestRefresher) Refresh(
	desired []domain.ComponentID,
) (executor.Preview, error) {
	if !reflect.DeepEqual(desired, refresher.request.Components) {
		return executor.Preview{}, errors.New(
			"refresh request differs from the reviewed component selection",
		)
	}
	reviewed, err := buildReviewedPlan(
		refresher.snapshots,
		cloneRequest(refresher.request),
	)
	if err != nil {
		return executor.Preview{}, err
	}
	if refresher.requireApplicable {
		if err := requireApplicableRefresh(reviewed); err != nil {
			return executor.Preview{}, err
		}
	}
	return reviewed.Executable(), nil
}

func requireApplicableRefresh(reviewed ReviewedPlan) error {
	if !reviewed.Applicable() {
		return errors.New("reviewed plan is no longer applicable")
	}
	return nil
}

func buildReviewedPlan(
	snapshots SnapshotBuilder,
	request Request,
) (ReviewedPlan, error) {
	snapshot, lifecycleRequest, semantic, err := buildSemanticPreview(
		snapshots,
		request,
	)
	if err != nil {
		return ReviewedPlan{}, err
	}
	prepared, err := snapshot.Lifecycle.PrepareConfiguration(lifecycleRequest)
	if err != nil {
		return ReviewedPlan{}, fmt.Errorf("prepare configuration preview: %w", err)
	}
	credentialChanges, credentialPrepared, err := prepareCredentials(
		snapshot,
		request,
	)
	if err != nil {
		return ReviewedPlan{}, err
	}
	prepared, err = configuration.CombinePreparedPlans(
		prepared,
		credentialPrepared,
	)
	if err != nil {
		return ReviewedPlan{}, fmt.Errorf(
			"combine configuration preview: %w",
			err,
		)
	}
	executable := executor.Preview{
		Release:       snapshot.Release,
		Desired:       append([]domain.ComponentID(nil), request.Components...),
		Plan:          cloneDomainPlan(semantic.Filesystem),
		Configuration: prepared,
	}
	credentialOnlyApplicable := len(credentialChanges) > 0 &&
		len(executable.Plan.Operations) == 0 &&
		credentialcatalog.IsInstancesOnlyPlan(prepared)
	return ReviewedPlan{
		request: cloneRequest(request), semantic: cloneSemantic(semantic),
		executable:  cloneExecutable(executable),
		credentials: cloneCredentialChanges(credentialChanges),
		applicable: credentialOnlyApplicable ||
			context7Applicable(request, semantic, executable),
		credentialOnlyApplicable: credentialOnlyApplicable,
		reviewed:                 true,
	}, nil
}

func prepareCredentials(
	snapshot Snapshot,
	request Request,
) ([]credentialcatalog.InstanceChange, configuration.PreparedPlan, error) {
	if request.CredentialInstances == nil {
		return nil, configuration.PreparedPlan{}, nil
	}
	if snapshot.Credentials == nil {
		return nil, configuration.PreparedPlan{}, fmt.Errorf(
			"credential snapshot is unavailable",
		)
	}
	current := snapshot.Credentials.Instances()
	changes, err := credentialcatalog.PlanInstanceChanges(
		current,
		*request.CredentialInstances,
	)
	if err != nil {
		return nil, configuration.PreparedPlan{}, fmt.Errorf(
			"plan credential instances: %w",
			err,
		)
	}
	prepared, err := snapshot.Credentials.Prepare(
		*request.CredentialInstances,
	)
	if err != nil {
		return nil, configuration.PreparedPlan{}, fmt.Errorf(
			"prepare credential instances: %w",
			err,
		)
	}
	return changes, prepared, nil
}

func cloneRequest(request Request) Request {
	cloned := Request{
		Components:    append([]domain.ComponentID(nil), request.Components...),
		MCPSelections: cloneSelections(request.MCPSelections),
		MCPCredentials: append(
			[]MCPCredentialBinding(nil),
			request.MCPCredentials...,
		),
		Diagnostics: request.Diagnostics,
	}
	if request.CredentialInstances != nil {
		instances := request.CredentialInstances.Clone()
		cloned.CredentialInstances = &instances
	}
	return cloned
}

func cloneCredentialChanges(
	changes []credentialcatalog.InstanceChange,
) []credentialcatalog.InstanceChange {
	result := make([]credentialcatalog.InstanceChange, len(changes))
	for index, change := range changes {
		result[index] = credentialcatalog.InstanceChange{
			Kind:   change.Kind,
			Before: change.Before.Clone(),
			After:  change.After.Clone(),
		}
	}
	return result
}

func cloneSelections(selections []mcpcatalog.Selection) []mcpcatalog.Selection {
	result := make([]mcpcatalog.Selection, len(selections))
	for index, selection := range selections {
		result[index] = selection
		result[index].Adapters = append(
			[]domain.ComponentID(nil),
			selection.Adapters...,
		)
	}
	return result
}

func cloneSemantic(preview lifecycle.Preview) lifecycle.Preview {
	return lifecycle.Preview{
		Filesystem: cloneDomainPlan(preview.Filesystem),
		Configuration: configuration.Plan{
			Changes:       append([]configuration.Change(nil), preview.Configuration.Changes...),
			Issues:        append([]configuration.Issue(nil), preview.Configuration.Issues...),
			ManualActions: append([]configuration.ManualAction(nil), preview.Configuration.ManualActions...),
			Notices:       append([]configuration.Notice(nil), preview.Configuration.Notices...),
		},
		MCP: mcpconfiguration.Plan{
			Intents:    append([]mcpconfiguration.Intent(nil), preview.MCP.Intents...),
			Migrations: append([]mcpconfiguration.MigrationAssessment(nil), preview.MCP.Migrations...),
			Blocking:   preview.MCP.Blocking,
		},
		Diagnostics: diagnostics.Plan{
			Intents:    append([]diagnostics.Intent(nil), preview.Diagnostics.Intents...),
			Executable: preview.Diagnostics.Executable,
		},
	}
}

func cloneExecutable(preview executor.Preview) executor.Preview {
	return executor.Preview{
		Release:       preview.Release,
		Desired:       append([]domain.ComponentID(nil), preview.Desired...),
		Plan:          cloneDomainPlan(preview.Plan),
		Configuration: preview.Configuration,
	}
}

func cloneDomainPlan(plan domain.Plan) domain.Plan {
	return domain.Plan{Operations: append([]domain.Operation(nil), plan.Operations...)}
}
