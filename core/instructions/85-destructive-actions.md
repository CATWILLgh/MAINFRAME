## Destructive actions

- Before any destructive or irreversible action — name it explicitly, list the specific files or scope affected, justify why it is necessary, and wait for the user's explicit acknowledgement.
- Destructive includes: force-push to any shared branch, recursive delete with broad scope, schema drops, mass file rewrites across many files, modifying or deleting data outside the current working directory.
- If a tool returns a permission denial — do not retry with different syntax to bypass the block. Report what was blocked, what you were trying to do, and ask for guidance.
