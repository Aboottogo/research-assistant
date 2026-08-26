# Scite — precise bibliographic records and citation-context evidence (MCP tool)

Requires the Scite MCP connector to be installed and connected; there is no public REST
fallback. The `mcp__scite__search_literature` tool covers ~210M papers. Two things it does better
than the other databases: (1) **bibliographic fidelity** — its records usually carry the
correct issue year, volume, issue, and pages (it had the JFE five-factor paper exactly
right: 2015, 116(1), 1-22); (2) **Smart Citations** — quoted statements from citing
papers classified as supporting / contrasting / mentioning, with a per-paper tally.
Use it for: verifying and completing citations, adjudicating claims via citation
context, and targeted retrieval of known papers. It is weak at **discovery ranking**.

## Quota — read first

Every call counts against a small fixed budget (hundreds of calls monthly on this
account). Waste comes from oversized payloads, not from thinking: **never call with the
default limit.** Plan queries before calling; a typical question needs 2-5 calls.

## Using it well

- **Always set `limit`: 3-5 on ANY call that has a `term`, `title`, or other search
  parameter** — at limit 10 those payloads (citation snippets + access blocks) routinely
  overflow the context window and the call is wasted. Only pure metadata fetches
  (`dois`/`titles` with no `term`) tolerate limit 10+. To see more of a result set,
  paginate with `offset` at a small limit rather than raising the limit.
  Payload size is CONTENT-driven, not just limit-driven: results that are review
  articles carrying hundreds of citation entries can overflow even at limit 4. When a
  call does overflow, the harness usually spills the full result to a local file —
  parse that file (jq/python) instead of re-spending quota on a re-query.
- **Fetch known papers by DOI**: `dois: [...]` with no `term` returns clean metadata +
  tallies for up to dozens of papers in ONE call. This is the cheapest, highest-value
  call the tool has. `titles: [...]` works when you lack DOIs.
- **Ranking is lexical, not authority-weighted.** A term search for a classic anomaly
  returns textbook chapters and minor variants before the seminal papers. To surface
  classics, add `citing_publications_from: 100` (or higher), or come in with titles.
- Term syntax supports AND/OR/NOT, "exact phrase", and proximity ("a b"~5). Use
  specific technical vocabulary; the index is cross-discipline.
- **`titles` is fuzzy, not exact** — a titles batch can return entirely unrelated
  papers (a cloud-computing paper for an earnings-management title). Check each hit's
  DOI/title before trusting the match; prefer `dois` whenever you have them, and the
  `title` + `author` field filters for known-item lookups.
- `dois` + `term` together searches *within* those papers' full text — good for
  checking what a specific paper actually says.

## Reading the results (the landmines)

- **Working papers**: a record with DOI prefix `10.2139/` (SSRN) and no `journal` field
  is a working paper — label it `[working paper]`. The published version is a separate
  record under its own DOI with `journal`/volume/pages populated; prefer it.
- **`year`/`date` can be the online-first year**, not the citable issue year — commonly
  one year early for AAA/Wiley journals (a TAR 99(1) 2024 article listed as 2023, a JAR
  55(1) 2017 article as 2016), while Elsevier records usually carry the issue year.
  Volume/issue/pages are reliable; when volume+journal imply a different year than the
  record, the issue year is the citable one.
- **JSTOR-era records** may carry only the first page ("159") — the range needs another
  source.
- **Authors can be genuinely missing** from a record (not just truncated); citation
  snippets inside the results often reveal the canonical author string ("Foster, Olsen
  and Shevlin 1984") — use them as corroboration, and say when a name isn't
  tool-verified. And in `author`-filtered searches the matched author is HOISTED to
  first position — author ORDER from such results is not tool-verifiable.
- Smart-citation tallies measure engagement, not quality; `contrasting` counts are the
  interesting signal worth reporting when adjudicating a claim.
- Check `editorialNotices` on anything you rely on; surface retractions/corrections.
