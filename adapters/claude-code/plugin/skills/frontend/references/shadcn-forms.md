# Forms

This file governs shadcn markup. Form state, schema validation, server
contracts, and tests remain in the core `frontend` route.

- Prefer the installed Field, FieldGroup, FieldSet, and FieldLegend primitives over layout-only wrappers.
- A visible label should identify each control. Instructions and errors must be programmatically associated with it.
- Put `data-invalid` on Field and `aria-invalid` on the control when that is the installed component contract.
- Put `data-disabled` on Field and `disabled` on the control.
- InputGroup contains InputGroupInput or InputGroupTextarea; actions inside it use InputGroupAddon.
- Grouped checkboxes and radios use FieldSet and FieldLegend.
- Use the installed selection primitive that matches the choice: Checkbox for independent choices, RadioGroup or ToggleGroup for one-of-many choices, Select or Combobox for larger sets.
- Preserve entered values after recoverable submission failures.
- Show pending state without allowing duplicate submission, and show errors near the failed field or operation.

Verify exact names and nesting against the installed source and current component documentation; shadcn source belongs to the project and may have been customized.
