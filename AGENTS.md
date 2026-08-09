# Shared repository constraints

These rules apply to every agent working in this repository, regardless of its
runtime role.

- Follow the role and bounded task supplied by the immediate caller. Do not
  assume that you own user communication, requirements discovery, acceptance
  criteria, orchestration, or final delivery unless the task explicitly assigns
  that responsibility.
- Do not repeat or override work completed by an upstream agent. Return the
  requested evidence or artifact to the caller within the assigned scope.
- Ground consequential technical claims in direct inspection, reproducible
  experiments, or current authoritative sources. Match the depth of validation
  to the uncertainty and cost of being wrong.
- Surface conflicting instructions to the caller instead of inventing a role
  that attempts to satisfy incompatible responsibilities.
- Do not restore the removed multi-adapter compilation system, release
  lifecycle, or terminal interface without a new explicit project decision.

The confirmed product decisions and the current interview state are recorded in
[docs/principles.md](docs/principles.md). Consult it before changing instruction
placement, primary-agent behavior, delegation, or delivery boundaries.
