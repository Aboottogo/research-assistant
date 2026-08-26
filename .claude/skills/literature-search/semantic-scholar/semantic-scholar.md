# Semantic Scholar — citation graph, recommendations, and full-text snippets

Semantic Scholar (S2) covers ~220M papers with a strong citation graph (including quoted
citation contexts and "influential citation" flags), paper recommendations, TLDR
summaries, and full-text snippet search. In finance/accounting its **bibliographic
metadata is often degraded** (see Landmines) — use S2 to *find and connect* papers, and
treat what it says *about* them as provisional.

## Tool

`scripts/s2.py` (python3 + requests). Set `S2_API_KEY` (free from
semanticscholar.org/product/api) for a dedicated 1 req/s lane; without it you share a
strict public pool and should expect 429 retries. The script rate-limits itself either way.

```
python3 semantic-scholar/scripts/s2.py <subcommand>

search "real earnings management cost of capital" -n 10 [--year 2015-] [--venue "..."]
       [--min-citations 50] [--pub-types Review]
bulk '"post-earnings announcement drift" -conference' --sort citationCount:desc -n 20
paper DOI:10.1016/j.jfineco.2014.10.010          # one record + TLDR + OA pdf link
match "Does Recognition versus Disclosure Affect Debt Contracting"   # best title match
citations DOI:10.1016/j.jacceco.2004.06.003 -n 10 [--contexts] [--by-cites]
refs DOI:10.2308/tar-2019-1066 -n 20 [--by-cites]
author "Katherine Schipper" -n 15
batch DOI:10.2307/2490232 DOI:... [up to 500]      # many papers, one call
recommend DOI:10.1016/j.jacceco.2004.06.003 [more seed ids...] -n 10
snippets "accruals quality priced risk factor" -n 5
```

Paper ids: `DOI:...`, `CorpusId:...`, or a raw S2 paperId. Output line:
`DOI | date | venue | authors | title (cites=N)`, with `[WP]` and
`[venue missing — verify elsewhere]` flags. `--json` for full records.

Distinctive capabilities worth reaching for:
- `citations --contexts` quotes the sentences where the citing paper uses the work —
  fast evidence for *how* a paper is used (supportive, critical, in passing).
- `citations --by-cites` ranks citing papers by their own citation counts (pages through
  up to `--max-edges` 3000 edges; a few seconds) — "most influential papers citing X".
- `recommend` finds similar papers from seed papers — good when keywords are failing.
- `snippets` searches inside full text across the corpus — good for locating passages
  or methods that titles/abstracts won't surface.
- `bulk` supports boolean syntax (`+` require, `-` exclude, `|` or, `"phrase"`) and
  server-side `--sort citationCount:desc` — the cheap way to list a topic's classics.

## Landmines

- **Metadata is not citation-grade here.** For major finance/accounting papers S2
  frequently has: empty venue/journal, null publicationDate, and a `year` equal to the
  working-paper year, not the journal year (the five-factor JFE 2015 paper is `year:
  2013, venue: ""` in S2; a 2024 TAR paper carries `publicationDate: 2023-03-01`).
  Journal names can even be flat wrong. Never put an S2 year/venue into a citation
  without confirming it against the publisher record.
- **SSRN DOIs are unstable anchors — and sometimes the only anchor.** SSRN repoints a
  DOI to the latest posted draft; S2's record under an SSRN DOI can be an *early* draft
  with a different title than the paper you mean. Worse, for some published papers S2
  holds the journal metadata ONLY under the SSRN/working-paper DOI and has no record at
  all under the journal DOI — so a "not found" on a journal DOI is not proof the paper
  is missing; try `match` on the title.
- **`--venue` filters match S2's venue strings exactly** and those strings are
  inconsistent or empty for finance/accounting journals — a venue filter can silently
  return nothing. Prefer a text query and filter the output yourself.
- **Digest/summary pollution.** CFA Digest and similar secondary items rank high in
  relevance search and can carry inflated citation counts. Check the venue before
  treating a hit as the primary paper.
- **Some venue strings are systematically corrupted**: every Auditing: A Journal of
  Practice & Theory record (DOI prefix `10.2308/aud`) carries the venue "Ear and
  Hearing" (an upstream audiology mismap). If a venue looks absurd for the topic,
  distrust the venue field, not the paper.
- **Author entities split across IDs, with stale records.** An author's top-ranked ID
  can list a published article only as its years-old SSRN working paper while a second
  ID holds the published version. Check the runner-up candidates the script prints, and
  never treat one author ID's list as an author's complete or current record.
- **The citation graph is a floor, not a census.** For some papers S2 holds no parsed
  reference list at all (`refs` returns nothing, and the paper then never appears in
  another paper's `citations` output even when it plainly cites it). Treat absent edges
  as unknown, not absent. The `isInfluential` flag is also unreliable — canonical
  rebuttals can go unflagged while routine applications are flagged.
- **DOI casing.** S2 returns some DOIs uppercased; the script lowercases them.
- **Rate limits.** 1 req/s with a key. The `--by-cites` paging and multi-call sessions
  are fine; parallel invocations of the script are not (each process rate-limits only
  itself — run one at a time).
