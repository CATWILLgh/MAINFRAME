# Desktop and CLI divergence

## Use when

Desktop and CLI expose different versions, configuration roots, component
catalogs, reload behavior, permissions, or hook events.

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

State whether configuration is shared and name any surface-specific unsupported
capability. Do not hide divergence behind one combined success claim.

## Never do

Never infer Desktop from CLI parsing, overwrite app-owned data to force sharing,
or create unverified symlinks between product roots.
