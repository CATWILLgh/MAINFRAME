# Forms and validation

- Preserve the project's established form approach. Native form state, React actions, React Hook Form, Formik, and framework actions are valid in different flows.
- Use native controls and the simplest state model that faithfully covers the interaction. A library is justified by repeated fields, dynamic arrays, complex validation, performance, or an established project convention—not by an arbitrary input count.
- Keep labels visible, associate descriptions and errors programmatically, preserve keyboard submission, focus the first relevant error when appropriate, and prevent accidental duplicate submission.
- Client validation improves feedback; the server remains responsible for protected rules and durable state. Reconcile server field errors with the form's existing error model.
- Use the project's existing runtime validator when schemas are part of the contract. Do not introduce Zod, Yup, or Valibot solely to validate one trivial local field.
- Treat loaded server data as an initial snapshot or explicit reset source, not a mutable alias of cached data. Preserve unsaved user input when a background refresh occurs unless the product explicitly replaces it.
- Test observable behavior: input, error text, disabled or pending state, submission, server rejection, and recovery. Avoid assertions on form-library internals.

Sources:
- React forms — https://react.dev/reference/react-dom/components/form
- React Hook Form — https://react-hook-form.com/
- WAI form instructions — https://www.w3.org/WAI/tutorials/forms/instructions/
