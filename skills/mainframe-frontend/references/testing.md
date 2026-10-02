# Frontend testing

Use `mainframe-testing` for red/green/refactor, the lightweight local PostgreSQL boundary, and CI ownership. Apply the stack-specific details below within that boundary; real service-backed checks beyond local PostgreSQL run in CI by default.

Use the project's existing runner, setup, fixtures, and browser harness. Establish
the command's scope and side effects when unknown or changed: it may start
services, migrate data, launch a browser, or rewrite files. Reuse current evidence
for subsequent runs of the same check.

Choose the smallest faithful boundary. Test business-facing transformations and state transitions without rendering when possible. Use component tests for rendered interaction, focus, accessibility state, form feedback, and data presentation. Use a real browser when navigation, layout, focus, motion, browser APIs, downloads, or a complete journey are the risk.

Protect only the reachable states and transitions relevant to the change. Prefer accessible queries and observable outcomes over private state, implementation-specific calls, snapshots, or mock call order. Keep owned fast collaborators real and replace external systems at their boundary.

Begin with focused evidence that fails for the reported behavior before changing the implementation, then run the repaired proof and nearest relevant fast checks. Broad or expensive suites belong in CI or a specifically authorized local pass.

Automated tests do not replace rendered browser acceptance. Report the exact behavior proved, the environment used, and every untested boundary.
