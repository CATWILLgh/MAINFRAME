# Small, reusable tool profiles

Use this method when selecting, installing, updating or connecting formatters, linters, type checkers, unused-code detectors or security analyzers. Static analysis complements behavioral tests; a clean analyzer result is not proof of application correctness.

## Resolve the project profile

1. Inspect the affected package's language, manifests, lockfiles, existing configuration, scripts and CI. In a monorepo, use its owning workspace rather than assuming one root-wide toolchain.
2. Reuse existing suitable project tools and commands. Identify a concrete missing guarantee before adding another analyzer; do not replace an established tool merely to match a preferred stack.
3. Select only applicable capabilities: formatting, linting, type checking, unused-code/dependency analysis, or security rules. One tool can cover several capabilities; do not install a tool per category or require every category for every language.
4. For an unfamiliar language, use its existing build/toolchain checks first and consult current authoritative documentation for remaining gaps. Reuse the installation and execution patterns below. Do not invent package names, flags, compatibility ranges or parser support.
5. Verify the bounded check actually runs, understands the relevant files/configuration and returns interpretable results. A version command proves executable availability only. Preserve the working profile in the existing project verification map; do not create another registry or documentation system.

The profile is a small set of facts, not a new package manager. For each selected tool record its purpose and applicable scope, existing configuration/command owner, installation/version owner, read-only invocation and limits, and how success, findings and execution failure are distinguished. Link manifests and scripts instead of copying their versions or configuration into prose. Preserve gaps explicitly.

## Reuse these installation patterns

| Owner | Pattern |
| --- | --- |
| Project toolchain provides the check | Use its established version and native command; add no competing runtime |
| Project dependency provides the check | Use the project's package manager, manifest and lockfile; reuse its compatible environment and CI setup |
| Standalone helper is justified | Use a maintained isolated tool environment with a recorded package source/version and update route; avoid polluting system packages |
| MAINFRAME hook depends on an analyzer | Use the maintained MAINFRAME installer and its tested compatibility contract; a project tool is not an interchangeable replacement merely because its executable name matches |

Prepare missing dependencies during authorized project setup or MAINFRAME installation, before relying on the check. Do not download packages or silently update versions inside a hook. Avoid launch commands that may install implicitly in the execution path. Resolve installation explicitly, then invoke the prepared executable. An offline or failed installation is an unavailable check with a concrete cause, not a passing result.

Use the same rule/configuration semantics in local checks, hooks and CI where they claim the same guarantee. Honor project lockfiles; for managed hook tools preserve the installer-tested version until compatibility is verified. Maintain an explicit update route rather than abandoned pins or uncontrolled latest-version downloads. Do not swap tools or loosen versions behind an existing output parser.

## Keep execution small and useful

Use read-only modes by default; formatting fixes and other mutations require the implementation task's authority and an attributable diff. Bound duration, parallelism and output. Limit analysis to the affected package/files when the tool can preserve the claimed guarantee; dependency graphs and type checks may need a broader package boundary. Never advertise a partial-file check as whole-project proof.

A hook executes an already prepared, applicable check. It must not provision services, repeatedly rediscover the toolchain, run the full suite or trigger model continuations merely to repeat an advisory. Report actionable new findings and deduplicate unchanged diagnostics. An unavailable tool/configuration or timeout is distinct from no findings; report the gap without flooding subsequent events. Scope any reuse of prior results to the relevant inputs, configuration and tool version.

Keep the default profile small and quick. Move necessary broad checks into their defined CI jobs; CI is not a reason to introduce every available scanner. SonarQube or comparable hosted/server analysis platforms require an explicit user request and agreement on purpose, scope, infrastructure, code/data transfer, cost and maintenance before adding them. A generic request to improve tests or CI does not authorize such a platform. Existing approved platforms may be reused within their agreed scope without repeating that decision.

## Audit the same profile

`mainframe-test-audit` evaluates whether the selected tools protect a concrete guarantee, use the intended configuration/version, run at the claimed scope, and report failures honestly. Treat unjustified duplication, expensive setup and missing dependencies as findings only with evidence of their effect. Do not install additional tools during a read-only audit or mark an existing project defective solely for lacking a preferred analyzer.
