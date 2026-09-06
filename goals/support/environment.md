# Establish the current environment

Before layer discovery, answer these questions from the supplied host context
and narrowly relevant native evidence:

- Which product and interface is executing this conversation: Desktop app,
  terminal CLI, IDE extension, or another surface? What observation establishes it?
- Which workspace is active, and which operation did the operator request?
- Which installed host version is actually known? Keep the model name, CLI
  version, and Desktop version separate. Unknown version alone does not require
  a broad search or prevent independent read-only inspection.
- Which configuration roots or shared mechanisms are already evidenced, and
  which remain to be established from the product's official documentation?

State the result briefly to the operator before inspecting installation layers:
"This run is in <product/interface>, established by <evidence>, for <operation>
in <workspace>. <Material unknowns>. Next I will establish <first layer>."
Fill this with observed facts; do not copy a product identity from an example,
the repository name, or an adjacent executable. The statement is a scope check,
not proof of the product's capabilities and not a request for confirmation.

Use that identity when selecting documentation for each layer. Announce a new
layer's question and later its supported result or gap in concise progress
updates, not a narration of every tool call. If evidence changes the identified
host or a shared configuration boundary, correct the statement and affected
conclusions before dependent work. Do not silently broaden the target.
