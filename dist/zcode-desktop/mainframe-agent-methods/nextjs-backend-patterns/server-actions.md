# Server Actions — `'use server'`

A `'use server'` function compiles to a **public POST endpoint**. Treat every one as an untrusted HTTP route — a hidden UI button protects nothing. Per Next: *"reachable via a direct POST request, not just through your application's UI."*

## The non-negotiable security rule

- **Validate args (Zod) AND authorize INSIDE the action, every time.** Per the Data Security guide: *"A page-level authentication check does not extend to the Server Actions defined within it."* Re-verify inside.
- Check **authorization, not just authentication** — does THIS user own THIS resource? *"check authorization (does this user have permission to act on this specific resource?)"* (IDOR).

## Mechanics

- `'use server'` at the top of a file (every export becomes an action) or inline in an async function.
- **Closed-over variables are encrypted** by Next when serialized client→server — but don't close over secrets needlessly.
- Action IDs are encrypted + non-deterministic, recalculated between builds.
- **Revalidate BEFORE redirect:** call `revalidatePath('/x')` / `revalidateTag('x')` *then* `redirect()` — *"Ensure fresh data… before redirect."*
- **`await cookies()` / `await headers()`** — these are **async in Next 15** (like `params`; `draftMode()` too); awaiting is required. Return serializable result state for `useActionState`.

## Discipline

- The action body is entry only: **validate → authorize → call a service/use-case → revalidate**. No business logic inline.
- Return typed result states (success / field errors) for form UX — don't throw raw errors at the client.
- **Rate-limit** expensive / sensitive actions — they are unauthenticated-reachable public POSTs; Next's production guidance recommends throttling them.

## Sources

- Server Actions security (public POST, re-verify inside, IDOR) — https://nextjs.org/docs/app/guides/data-security
- Updating data (revalidate before redirect) — https://nextjs.org/docs/app/getting-started/updating-data
