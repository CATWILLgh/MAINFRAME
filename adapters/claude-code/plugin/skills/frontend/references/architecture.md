# Frontend architecture

- Start from the architecture already carrying the active user flow. Trace routes, providers, public module boundaries, shared primitives, state ownership, and dependency direction before moving files.
- Keep code close to the user capability that owns it. Share a module only after more than one real consumer needs the same contract; do not grow generic `utils`, `hooks`, or `components` dumping grounds.
- Preserve existing public imports and package boundaries. A local change is not permission to reorganize the application.
- Separate rendering, interaction state, remote data access, and durable business authority where the distinction reduces coupling. Do not create layers that merely forward calls without owning a decision.
- Feature-Sliced Design is supported when the project already uses it or when a new architecture decision selects it. Respect its layer direction and slice public APIs in that case.
- Clean Architecture, route-oriented modules, package-by-feature, and a coherent flat structure are valid established designs. Improve the changed path within their rules rather than filing a ticket because they are not FSD.
- For new isolated code, follow the nearest coherent module pattern. Propose a broader migration only when the current result cannot be delivered safely without it.

Sources:
- React project structure guidance — https://react.dev/learn/thinking-in-react
- Feature-Sliced Design — https://feature-sliced.design/
