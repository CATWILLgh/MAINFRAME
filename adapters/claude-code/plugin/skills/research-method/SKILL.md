---
name: research-method
description: "Use only as the private standing research method of mainframe-researcher."
user-invocable: false
disable-model-invocation: true
---

# Research method

Research certainty is claim-local, not report-wide. Classify and verify each
material claim independently, then combine only findings that remain compatible.

## Boundary

- Work only from the question and project facts supplied by the caller plus
  external sources. Do not inspect the project or infer missing local state.
- Establish evidence. Do not recommend, select, or advocate for an option.
- Use English internally and in the returned package.
- Stop when decision-relevant external uncertainty is resolved. More links are
  not evidence when they repeat the same underlying source.

## Method

1. Normalize the question: entities, jurisdiction, product or dataset version,
   reference period, comparison baseline, units, and the date on which the
   answer must be current. Return a missing load-bearing input as a limitation.
2. Split the question into atomic, falsifiable claims. For each material claim,
   assign every applicable domain rather than one label for the whole report.
3. Read every applicable domain profile before researching that claim:
   - [Software documentation](references/software-documentation.md) for APIs,
     libraries, tools, protocols, releases, compatibility, and security notices.
   - [Economics and quantitative data](references/economics.md) for statistics,
     prices, rates, money, ratios, forecasts, surveys, and calculated changes.
   - [News and current events](references/news.md) for events, announcements,
     disputes, developing stories, and time-sensitive public claims.
   `WebSearch` and `WebFetch` are automatically rejected until at least one
   profile has been read. That gate proves preparation happened; it does not
   choose for you. When a claim crosses domains, read every matching profile,
   not merely the first one that unlocks the tools.
4. Prefer the closest authoritative primary source. Use a second independent
   source when the claim is disputable, interpretive, fast-changing, supplied
   by an interested party, or consequential enough that one source is fragile.
   A canonical fact may rest on one controlling primary source.
5. Trace provenance. Syndicated reports, copied tables, mirrors, and articles
   citing the same statement are one evidence chain, not cross-confirmation.
6. Match every number and date to the source before using it. Preserve units,
   scale, currency, timezone, reference period, publication date, revision
   status, and rounding. For a derived value, show the operands and formula and
   verify the arithmetic; if the available tools cannot verify it reliably,
   return the operands instead of asserting the result.
7. Record contradictions without averaging or silently selecting a convenient
   value. Explain whether they arise from timing, definitions, versions,
   methodology, corrections, or a genuinely unresolved conflict.
8. Re-open each load-bearing source before returning. Confirm that the cited
   page supports the exact nearby claim and that the result is current as of
   the research date.
9. Do not repeat a failed retrieval through superficial URL variants when the
   returned content or error is unchanged. After two genuinely different paths
   fail to expose claim-supporting content, record the limitation and continue
   with other evidence or stop.

## Return

Lead with a short plain-English summary of verified information. Then provide:

- evidence for each load-bearing claim with direct source links;
- exact numeric and temporal qualifiers where applicable;
- contradictions, limitations, version boundaries, and unresolved facts;
- the research `as of` date.

Do not narrate searches, paste long quotations, or manufacture balance. Keep
facts supplied by the caller visibly distinct from facts verified externally.
