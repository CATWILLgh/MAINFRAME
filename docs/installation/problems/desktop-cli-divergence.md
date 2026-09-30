# Desktop and CLI divergence

## Use when

The user explicitly requested both Desktop and CLI, and they expose different
versions, configuration roots, component catalogs, reload behavior, permissions,
or hook events. An ordinary installation on one surface does not open this route
merely because another surface is installed.

## Desired result

Each user-relevant surface has a verified effective installation, with shared
state used only where sharing is proven.

## Inspect

Record both versions, executables or app builds, effective config roots,
environment, discovery listings, hook dispatch, and whether one surface bundles
or launches the other.

## Adapt

Use one installation when both surfaces demonstrably share the same native
owner. Otherwise adapt each required surface under the same canonical identities
while keeping target registrations separate and explicit.

## Verify

Run the smallest native discovery and behavior probe in both surfaces. For GUI
behavior, use visible interaction; for CLI behavior, use its actual command path.

## Record

State whether configuration is shared and name each surface's version, delivery,
proof, and established limitation. Apply the aggregate rule in
[verification.md](../verification.md#desktop-and-cli): completed shared delivery
can be `installed` while an untested requested surface keeps verification
`pending`. An established product limitation makes delivery `unsupported` and
omits verification. Do not hide divergence behind one combined success claim.

## Never do

Never infer Desktop from CLI parsing, overwrite app-owned data to force sharing,
or create unverified symlinks between product roots.
