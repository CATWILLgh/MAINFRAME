# Forms — React Hook Form + Zod

Form state lives in `react-hook-form`. Validation lives in Zod schemas resolved via `@hookform/resolvers/zod`. Per RHF docs: `zodResolver` is the canonical bridge; auto-detects Zod v3 vs v4.

## Canonical pattern

```ts
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

const schema = z.object({
  email: z.string().email(),
  age: z.number().int().min(18),
})
type FormValues = z.infer<typeof schema>

const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({
  resolver: zodResolver(schema),
  defaultValues: { email: '', age: 18 },
})
```

`defaultValues` MUST be set explicitly — uncontrolled-to-controlled jumps cause React warnings and lose initial state.

## Form-state vs server-state separation

The form owns the *draft* the user is editing. The query cache owns the *server snapshot*. They never share the same store. Loading flow:

```ts
const { data: user } = useQuery({ queryKey: ['user', id], queryFn: fetchUser })
const form = useForm({ defaultValues: user, resolver: zodResolver(schema) })
useEffect(() => { if (user) form.reset(user) }, [user, form])  // sync on snapshot change
```

Submission flow: `handleSubmit` → `mutation.mutate(values)` → on success → `queryClient.invalidateQueries(['user', id])` → the next refetch re-seeds the draft via `form.reset`.

**Forbidden:** mutating the cached entity in place (`user.email = newEmail`) and submitting it. The cache is owned by TQ — mutating breaks invalidation logic.

## Zod v3 → v4

`@hookform/resolvers` ≥ v5 detects both automatically. If migrating: v4 schemas have stricter defaults around `z.string()` (no longer coerces by default). The recon outcome reports which is in the project — touch it only if scope explicitly allows.

## Disabled / loading state — wire `isSubmitting` to UI

```tsx
<Button type="submit" disabled={isSubmitting}>
  {isSubmitting && <Spinner data-icon="inline-start" />}
  Save
</Button>
```

The Spinner / `data-icon` markup lives in the companion `shadcn` skill (per the boundary). Disable + visual feedback are mandatory — double-submit is a frequent regression source.

## Server-side validation errors → setError per field

When the server rejects with a per-field error map, surface them via RHF:

```ts
mutation.mutate(values, {
  onError: (err) => {
    if (err.status === 422 && err.fields) {
      for (const [name, msg] of Object.entries(err.fields)) {
        form.setError(name as keyof FormValues, { type: 'server', message: msg })
      }
    }
  }
})
```

Generic toast for non-field errors. Per-field display only via `formState.errors`.

## Anti-patterns

- `useState` per field for a form with > 2 inputs — RHF exists for this.
- Bypassing Zod and validating in `onSubmit` with manual `if`s — schema-first is the rule.
- A `try { schema.parse(...) } catch` block in a click handler — that's resolver territory.
- Submitting a form on `onChange` of the last field — accidental submit anti-pattern.

## Sources

- React Hook Form — https://react-hook-form.com
- `@hookform/resolvers` Zod — https://github.com/react-hook-form/resolvers
- Zod v4 changelog — https://zod.dev/v4/changelog
