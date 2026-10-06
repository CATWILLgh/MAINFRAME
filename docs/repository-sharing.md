# Sharing the source repository

Use this guide before publishing MAINFRAME to another Git host or changing the
set of shared refs. It concerns repository disclosure, not global installation.
Publishing, pushing, remote changes and destructive history edits require their
own authorization.

## One portable source

Keep the same canonical component sources and maintained adapters across hosts.
Corporate endpoints, credential references, receiving-project knowledge and
personal configuration belong outside the shared source. A private destination
does not make such material suitable for a branch also published elsewhere.
Preserve the MIT license and legitimate author attribution.

Repository documentation, native evidence, tests and installation modules are
useful shared source. They are not global product payload. Dated native evidence
must name its tested version and distinguish source inspection, delivery,
discovery and live behavior. Use portable home-root notation and neutral
fixtures rather than actual receiving-project names or machine paths.

## Review the selected revision

Inspect tracked files and staged changes, rather than copying the working
directory. Local tickets, adaptation state, the credential index and maintainer
knowledge remain ignored under the source's [.gitignore](../.gitignore).
Ignored material that was forcibly tracked must be removed from tracking before
publication; ignore rules alone do not remove it.

Use filename-only checks first:

```sh
git status --short
git diff --cached --stat
git ls-files
git ls-files -ci --exclude-standard
```

Review source and supporting resources for unnecessary project provenance,
private URLs, machine paths, real credentials and session data. Preserve useful
neutral examples and synthetic scanner fixtures. Do not print suspected secret
values or place them in an audit report. Follow [SECURITY.md](../SECURITY.md)
if actual exposure is established.

Check the [exact payload inventory](../ADAPTATION.example.json) and each affected
adapter's rendered artifact set separately. The shared skill resource selector
excludes ignored files and Git control files; Git checkouts reject untracked
non-ignored resources. A downloaded archive has no index to establish ownership,
so build shared archives from a reviewed revision rather than a dirty local
directory. Source approval and native activation are separate claims.

## Review the history and refs

A selected branch includes its ancestors. A clean current tree does not remove
older project references, private files or commit-message details. A broad
mirror also includes additional refs and their history. Review the intended
branch/tag set before choosing the transfer method:

```sh
git for-each-ref --format='%(refname)' refs/heads refs/tags refs/remotes
```

When historical disclosure is unacceptable, obtain an explicit decision between
a reviewed source snapshot with a new lineage and scoped history sanitization.
Prepare the candidate separately and preserve the original refs until approved.
Do not automatically rewrite, force-push, delete legacy branches, or include
every local ref. Secret rotation and historical data removal are separate actions.

## Validation on each host

Run checks appropriate to the changed source through
[CONTRIBUTING.md](../CONTRIBUTING.md#validate-the-change). The maintained hosted
pipeline currently lives in [GitHub Actions](../.github/workflows/ci.yml).
Local results do not prove a hosted run for the selected revision.

Before relying on another host as a checked collaboration route, configure its
own pipeline, required merge checks, runner trust and private security-reporting
channel under separate authority. Preserve the same source guarantees. Do not
claim GitLab CI coverage from the GitHub workflow or a local test run, and do not
invent corporate runner, credential or visibility policy.
