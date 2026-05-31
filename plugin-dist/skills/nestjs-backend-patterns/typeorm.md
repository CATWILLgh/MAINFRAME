# TypeORM 0.3 patterns

Cross-framework Node.js ORM. Active maintenance is moderate (community-maintained, slower release cadence than Prisma/Drizzle). Heavy in NestJS + class-validator ecosystem. For new projects: consider Prisma or Drizzle. For existing TypeORM projects: discipline below.

## Entity + DataSource

- One `@Entity()` per table; columns via `@Column`, relations via `@ManyToOne` / `@OneToMany` / `@ManyToMany`.
- Single `DataSource` instance bootstrapped in `app.module.ts` (NestJS) or `dataSource.ts` (standalone). Avoid multiple data sources per service.
- TypeORM 0.3 removed `getRepository()` global helper — use `dataSource.getRepository(Entity)` or `@InjectRepository(Entity)` (NestJS).

## Repository pattern

Prefer **`Repository<T>`** + custom methods over raw query builder for typical CRUD:

```typescript
@Injectable()
export class JobsService {
  constructor(@InjectRepository(Job) private jobs: Repository<Job>) {}
  async findByMachine(machineId: string) {
    return this.jobs.find({ where: { machineId }, relations: { downtimes: true } });
  }
}
```

## Eager loading by cardinality

- `relations: { manyToOne: true }` — one JOIN, fine for single objects.
- `relations: { oneToMany: true }` — **N+1 trap if used on lists.** TypeORM does separate `IN` queries by default (good), but `eager: true` on the entity causes JOIN explosion. Disable `eager`, load explicitly per query.
- Anti-pattern: accessing relation in DTO mapper without explicit `relations` → lazy load fires N times.

## Locking

```typescript
await dataSource.transaction(async (manager) => {
  const shift = await manager.findOne(Shift, {
    where: { id }, lock: { mode: "pessimistic_write" },
  });
  if (shift.status === "completed") throw new ConflictException();
  shift.status = "active";
});
```

`pessimistic_write` = `SELECT FOR UPDATE`. Always wrap in `transaction` — lock scope is the txn.

## Migrations

- Generate: `typeorm-ts-node-commonjs migration:generate src/migrations/<name> -d data-source.ts`.
- Review diff before commit — TypeORM sometimes generates noise (column reordering, default changes that are no-ops).
- Up + down both required; raw SQL OK for non-trivial transformations (`queryRunner.query(...)`).

## Soft delete

`@DeleteDateColumn` makes `repository.softRemove()` / `repository.restore()` work; `find` auto-filters soft-deleted rows. For audit / compliance — prefer this over hard delete.

## Sources

- TypeORM 0.3 docs — https://typeorm.io/
