# MAINFRAME repository

MAINFRAME is an adapter-agnostic template hub. Read
[the product principles](docs/principles.md) before changing instruction
placement, role boundaries, native adaptation, or delivery.

- Work within the assigned task and preserve unrelated changes.
- Keep agent-facing source in English and operator documentation in Russian.
- Keep one useful method per skill, available to direct and delegated work.
- Read current official product documentation before making a native-contract
  claim; templates express outcomes, not verified support in every product.
- Do not reintroduce adapter implementations, installers, compilation,
  telemetry, or a custom goal lifecycle.
- Update [the disposable catalog](examples/progress.json) when source units
  change. Its only progress field is `done`, initially false.
- Preserve private credentials and user configuration. Do not read protected
  credential stores.
- Validate with `python3 scripts/check-hub.py` and `git diff --check`.
  Check actual behavior separately when it is the changed risk.
- Record observed harness problems in the local ticket queue and notify the
  operator. Never turn unfinished in-scope work into a deferred ticket.

Use [.agents/repository.json](.agents/repository.json) as a navigation hint;
verify claims against current source. Historical delivery and local runtime
bridges are not part of the current template catalog.
