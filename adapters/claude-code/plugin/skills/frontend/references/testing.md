# React frontend testing

Use the project's existing test runner and React testing setup. Protect the
user-visible behaviour changed by the task with the smallest test that can
catch its regression.

Before execution, inspect the selected package script, npm-compatible lifecycle
scripts, runner configuration, and setup reached by the focused test. A test
command can prepare or migrate a database, start a browser or service, rewrite
generated files, or depend on an external endpoint. Choose the narrowest
command whose effects match the current task and environment.

## Choose the surface

- Test pure business-facing transformations, validators, reducers, and state
  transitions without rendering a component.
- Use a component test when rendering, interaction, focus, accessibility state,
  form feedback, loading, error, or data presentation is the contract.
- Keep owned collaborators real when they are fast. Replace the network or
  external system at its boundary; do not assert the mock's private call order.
- Use browser end-to-end tests only when navigation, browser behaviour, or the
  complete user journey is itself the risk. Do not repeat every form branch in
  E2E after a cheaper component or logic test proves it.

Add success, invalid-input, empty, loading, error, retry, or permission
scenarios only when they exist in the changed user flow. Prefer accessible
queries and observable output over component internals, snapshots, private
state, or implementation-specific hook calls.

Do not duplicate the same guarantee across levels or leave temporary markers.

Automated checks prove technical behaviour. They do not replace product-owner
acceptance of the running UX and UI.

## Sources

- React Testing Library guiding principles — https://testing-library.com/docs/guiding-principles/
- Vitest — https://vitest.dev/guide/
- Playwright test best practices — https://playwright.dev/docs/best-practices
