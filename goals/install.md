# Install MAINFRAME

Execute this installation objective when the operator invokes this file through
the native goal mechanism. First load the agreed installation brief from the
explicitly supplied local file or current conversation. The brief must identify
this product and checkout and settle the choices in [the brief](../prompts/brief.md).
If it is missing, ambiguous, or still has pending answers, perform no installation
writes: explain that the briefing must be completed first. Do not invent choices
or begin an interview inside this execution goal. Do not create a second goal.

Install the materials in this repository into the current agent product's
global environment, adapting them to its actual capabilities.

Your first substantive step is to consult your own current official product
documentation for every relevant layer: global instructions, skills, commands,
hooks, subagents, tool restrictions, settings, and the native goal lifecycle.
Identify the actual product surface and version. Use the repository's templates
to identify the layers you need, not as evidence of product support. Do not
write installation files before this documentation pass.

Then follow [the adaptation procedure](support/adapt.md). Copy
[the progress example](../examples/progress.json) into a fresh local working
file and process every item sequentially, including its supporting resources.
Use only the boolean `done` marks to preserve progress for this run.

Deliver a small coherent installation, with all placeholders resolved, skills
usable by any authorized agent, and checks of the actual installed result.
Preserve unrelated configuration and credentials. Replace confirmed old
MAINFRAME delivery as part of installation; remove its obsolete telemetry
registrations without changing the user's unrelated observability settings.

Complete the goal only when every item is accounted for and the installed
behavior has been verified to the extent the current surface permits. Report
changed paths, official documentation used, checks actually observed, deliberate
unsupported omissions, and anything still blocked or requiring a user reload.
Do not describe an untested or blocked installation as fully working.
