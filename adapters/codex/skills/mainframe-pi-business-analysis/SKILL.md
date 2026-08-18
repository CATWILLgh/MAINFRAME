---
name: mainframe-pi-business-analysis
description: Run MAINFRAME's project-scoped Pi digital business analyst on a requirements statement or document package explicitly handed over for review. Use when the user asks to review that supplied requirements input. Do not use for ordinary discussion, planning, code research, or implementation.
---

# Pi business analysis

Keep ownership of user communication and product decisions in this primary
task. Pi is a read-only external worker that writes one evidence-grounded
Markdown review under `docs/initiatives/<slug>/reviews/`; it does not replace
the final decision or definition of done.

Use the current project as the analysis boundary. Choose one short stable
initiative slug. Pass only the requirements input explicitly handed over for
this review: `--statement` for the supplied short text, repeatable `--entry`
for named files inside the project, and repeatable `--input-file` for named
external files. Pass supplied statement text verbatim; do not summarize or
rewrite it. These forms may be combined into one bounded package. Do not
infer the package from ordinary conversation, planning context, or unrelated
task history. Do not invent a source path or broaden the project root. If no
explicit source was handed over, do not run the worker.

Run:

```sh
mainframe-pi business-analysis --initiative <slug> (--statement <text> | --entry <project-path> | --input-file <path>)... [--fresh-session]
```

The command may run for several minutes. Let it finish once; do not start a
second fresh run merely because it is slow. After completion, inspect the JSON
result and the reported review file. Treat `incomplete` as usable but limited
evidence, and `blocked` or a non-zero exit as a failed run. Report the review
path, run status, readiness, and material limitations plainly. Never present a
partial or missing review as completed analysis.
