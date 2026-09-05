# Software documentation research

Apply this guide to claims about software behavior, APIs, libraries, runtimes,
protocols, releases, compatibility, configuration, and security notices.

## Establish the target

- Identify the exact product, package, provider, surface, version or version
  range, platform, and release channel. A current latest-version answer does not
  establish behavior for the caller's installed version.
- Keep similarly named surfaces separate: CLI, desktop application, hosted
  service, API, SDK, extension, and plugin contracts are not interchangeable.
- Treat preview, beta, release-candidate, canary, and deprecated behavior as
  distinct from stable behavior.

## Source order

1. Official versioned reference or specification for the exact surface.
2. Official release notes, migration guide, changelog, or security advisory for
   when behavior changed.
3. Official registry metadata, release, or tag for version and channel facts.
4. Upstream source, tests, types, or maintainer issue only when official prose
   leaves the behavior unresolved; label implementation evidence as such.
5. Secondary technical material only to locate primary evidence or expose a
   conflict. Never let it override the owning project's current contract.

Use Context7 to locate version-relevant official material, then cite the
underlying official source whenever it is available.

## Verification

- For an API claim, verify the exact symbol, signature, defaults, constraints,
  return shape, errors, and version boundary relevant to the question.
- For a change claim, establish both sides of the boundary and the first release
  where the new behavior applies. Do not infer compatibility from a version
  number alone; not every project follows Semantic Versioning correctly.
- Distinguish a Git tag, repository release, package-registry version, and a
  moving channel label such as `latest`, `stable`, `next`, or `canary`.
- Check the page's selected version, last-updated state, and archived banners.
- When docs and observable implementation disagree, report both and identify
  which one is the published contract. Do not resolve the conflict by memory.

## Cross-domain composition

Also apply [news.md](news.md) to a new announcement, incident, vulnerability,
acquisition, roadmap claim, or developing release story. Apply
[economics.md](economics.md) when the claim compares prices, usage, benchmarks,
market share, costs, or calculated performance differences.

## Method sources

- [Semantic Versioning 2.0.0](https://semver.org/)
- [GitHub documentation: releases and tags](https://docs.github.com/en/repositories/releasing-projects-on-github/viewing-your-repositorys-releases-and-tags)
- [npm documentation: distribution tags](https://docs.npmjs.com/cli/dist-tag/)
