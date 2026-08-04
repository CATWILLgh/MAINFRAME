# Express patterns

Most-deployed Node web framework (68% State of JS 2024). Minimalist — bring your own ORM, validation, auth. Best when project needs minimal abstraction or has legacy weight. For new enterprise work — usually NestJS (DI structure) or Fastify (perf).

## App structure

- One `app.ts` exports the Express app; `server.ts` starts the HTTP listener (separation enables testing the app in-process).
- Routes split by resource into `routes/<resource>.ts`. Mount in `app.ts`: `app.use("/v1/jobs", jobsRouter)`.
- Middleware order matters: parse body → logging → auth → routes → error handler. Error handler is LAST and has 4-arg signature `(err, req, res, next)`.

```typescript
const app = express();
app.use(express.json({ limit: "1mb" }));
app.use(pinoHttp());
app.use("/v1", apiRouter);
app.use(errorHandler);
```

## Async handlers and error propagation

Express 4 does NOT auto-forward async errors. Wrap or use Express 5 (default since ~2024 prod-ready):

```typescript
router.post("/jobs", async (req, res, next) => {
  try {
    const job = await jobsService.create(req.body, req.user);
    res.status(201).json(job);
  } catch (e) { next(e); }
});
```

Or `import "express-async-errors"` once — it patches Express 4 to forward async exceptions automatically. Express 5 removes the need.

## Validation

No built-in. Pick one:
- **Zod** — schema-first, types inferred — works directly. Pattern: `const dto = JobSchema.parse(req.body)`.
- **express-validator** — chain-based middleware. Older convention.

Always validate at the controller boundary; never trust `req.body` shape.

## Authentication

- Library: `passport` + `passport-jwt` (or `passport-local`). Or bare `jsonwebtoken` + custom middleware.
- HTTP-only cookies for refresh tokens; short-lived access tokens (15min).
- Tenant + role data in JWT claims; verify in auth middleware, attach to `req.user`. NEVER accept `organization_id` from body.

## Error handler

```typescript
const errorHandler = (err: any, req: Request, res: Response, next: NextFunction) => {
  logger.error({ err, path: req.path }, "request failed");
  if (err instanceof ZodError) return res.status(400).json({ errors: err.issues });
  if (err.status) return res.status(err.status).json({ error: err.message });
  res.status(500).json({ error: "internal" });
};
```

Never let stack traces reach the client in prod.

## Sources

- Express docs — https://expressjs.com/
