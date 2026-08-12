# Context and direction

Keep three kinds of context distinct:

1. **Product truth** — audience, user jobs, business behavior, content, constraints, and failure consequences.
2. **Design contract** — established tokens, typography, primitives, interaction patterns, brand character, and accessibility expectations.
3. **Surface direction** — the dominant mode, local user journey, representative states, and any intentional exception for the current surface.

Find these in existing project files and the running product before creating new documentation. Do not require files named `PRODUCT.md` or `DESIGN.md`; a repository may already express the same truth through another canonical source. Treat current behavior as evidence, not automatic truth. If sources conflict and repository evidence cannot resolve them, surface the product decision instead of silently choosing one.

Create or update a durable design document only when the task authorizes it and the decision will be reused. Keep it human-readable, link to deeper sources instead of copying them, and record intent alongside tokens so future agents understand why a rule exists. A short surface brief is useful for a substantial new direction or redesign, not as ceremony for every component change.

Load only the relevant portions during implementation. Product and design documents are memory, not a prompt bundle that must be injected in full on every turn.

## Direction test

A direction is ready when it explains:

- whom the surface serves and what they must accomplish;
- which mode dominates and why;
- what existing language must be preserved;
- which content and states are representative;
- which visual choices are intentional rather than untouched defaults;
- which accessibility, platform, performance, or brand constraints bound the result.

Do not treat a trend, a random seed, or a list of forbidden aesthetics as a direction.

## Sources

- Google design.md specification — https://github.com/google-labs-code/design.md/blob/main/docs/spec.md
- Google design.md philosophy — https://github.com/google-labs-code/design.md/blob/main/PHILOSOPHY.md
- Apple design principles — https://developer.apple.com/design/human-interface-guidelines/design-principles
