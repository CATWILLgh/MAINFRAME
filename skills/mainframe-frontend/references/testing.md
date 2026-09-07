# Frontend testing

Use the project's existing runner, setup, fixtures, and browser harness. Inspect the selected package script, lifecycle hooks, configuration, and reached setup before execution; a test command may start services, migrate data, launch a browser, or rewrite generated files.

Choose the smallest faithful boundary. Test business-facing transformations and state transitions without rendering when possible. Use component tests for rendered interaction, focus, accessibility state, form feedback, and data presentation. Use a real browser when navigation, layout, focus, motion, browser APIs, downloads, or a complete journey are the risk.

Protect only the reachable states and transitions relevant to the change. Prefer accessible queries and observable outcomes over private state, implementation-specific calls, snapshots, or mock call order. Keep owned fast collaborators real and replace external systems at their boundary.

Begin with focused evidence that fails for the reported behavior when practical, then run the repaired proof and nearest relevant fast checks. Broad or expensive suites belong in CI or an explicitly requested full pass unless the changed risk cannot be established otherwise.

Automated tests do not replace rendered browser acceptance. Report the exact behavior proved, the environment used, and every untested boundary.
