# Software documentation research

Apply this reference to claims about software products, APIs, libraries, runtimes, protocols, releases, compatibility, configuration, incidents, and security notices.

## Identify the exact surface

Establish the product, provider, package, API or protocol, version or version range, platform, release channel, and relevant date. Keep CLI, desktop, hosted service, API, SDK, extension, plugin, and administrative surfaces separate. Do not generalize preview, beta, release-candidate, canary, deprecated, or moving-channel behavior to a stable release.

The current latest-version contract does not establish behavior for an installed older version. When the local version matters, obtain it from local evidence supplied or inspected under the active assignment; do not infer it from external documentation.

## Prefer owning sources

Use this evidence order:

1. Official versioned reference or specification for the exact surface.
2. Official release note, migration guide, changelog, incident report, or security advisory that establishes when behavior changed.
3. Official registry metadata, release, tag, or support matrix for version and channel facts.
4. Upstream source, tests, types, or maintainer issue when official prose leaves the behavior unresolved; label this as implementation evidence rather than the published contract.
5. Secondary technical material only to locate primary evidence or expose a conflict.

An available documentation index may help locate the official corpus, but cite and evaluate the underlying owning source whenever it is accessible.

## Verify the claimed behavior

For an API or configuration claim, verify the exact symbol or key, signature or schema, defaults, constraints, return shape, errors, side effects, and version boundary relevant to the question.

For a change claim, establish both sides of the boundary and the first release where the new behavior applies. Distinguish repository tags, release pages, registry versions, and moving labels such as `latest`, `stable`, `next`, or `canary`. Do not infer compatibility from a version number alone.

Check the selected documentation version, archived or preview banners, publication or update date, and support status. When documentation and observable implementation conflict, report both and identify which is the published contract; do not silently resolve the conflict from memory.

Also apply [news and current events](news.md) when the claim concerns a new announcement, public incident, vulnerability, acquisition, roadmap, or developing release story. Apply [quantitative data](quantitative-data.md) when it compares prices, usage, benchmarks, costs, or calculated performance.
