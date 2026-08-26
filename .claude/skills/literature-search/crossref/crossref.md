# Crossref — bibliographic lookup, verification, and working-paper resolution

Crossref is the DOI registration agency: its record for a DOI is the publisher-deposited,
citation-grade metadata (authors, journal, volume/issue/pages, dates). It is authoritative
for **what a DOI is**, and mediocre at **finding papers by topic** — its relevance ranking
is loose OR-matching, and working papers often outrank the journal versions of famous papers.

Use it to: verify citations exist and are correctly described; get citable metadata for a
known DOI; resolve a working paper to its published version; find a paper by title+author.
Do not use it for: topical discovery, ranked literature reviews, citation counts.

## Tool

`scripts/crossref.py` (python3 + requests; no key needed). Pass your email once per call
with `--mailto you@university.edu` — it routes you to Crossref's faster "polite" pool.

```
python3 scripts/crossref.py --mailto YOU@EXAMPLE.EDU <subcommand>

search "pension accounting value relevance" --rows 10 [--type journal-article]
       [--container "Journal of Finance"] [--author fama] [--from-year 2015] [--until-year 2024]
doi 10.2308/tar-2019-1066 [more DOIs...]        # canonical record + date breakdown
published "A Five-Factor Asset Pricing Model" --author Fama   # WP title -> journal version
verify "10.2307/2490232 :: An Empirical Evaluation of Accounting Income Numbers" [...]
```

Output line: `DOI | year | container vol(iss):pages | authors | title`, working papers
flagged `[WP]`. Add `--json` for the full record. `verify` exits nonzero on any failure —
run it on every citation list before delivering it (it catches hallucinated DOIs and
DOI-title mismatches).

## Landmines

- **Dates.** `issued` is the *earliest* known date and is often the online-first date:
  an article in a January-2024 issue can carry `issued: 2023-12-11`. The script's
  `citable=` line already prefers `published-print`; trust it over raw `issued`, and
  never use `created` (that is a registration timestamp).
- **Working papers.** SSRN records are `type: posted-content` — but not always: some are
  mis-typed `journal-article` with container "SSRN Electronic Journal". NBER working
  papers are `type: report`. The script's `[WP]` flag checks type, container, and the
  `10.2139/…` (SSRN) / `10.3386/…` (NBER) DOI prefixes together; a `--type journal-article`
  filter alone does NOT remove all working papers.
- **No preprint links for SSRN/NBER.** Crossref's `relation.is-preprint-of` field is
  essentially never populated for finance/economics working papers. The only way to find
  the published version is bibliographic re-search — that is what `published` does
  (title-similarity ≥ 0.5 against journal articles; titles often change between the WP
  and the journal version, so on a miss, retry with distinctive title words + `--author`).
- **Search pollution.** Relevance search surfaces CFA Digest summaries, comment/reply
  pieces, and regional lookalikes above the paper you mean. `search` is for "find this
  known thing", not for surveying a literature; keep `--rows` small and read critically.
- **Truncated pages.** Some deposits (notably JSTOR-era) record only the first page
  ("159", not "159-178").
- **`--container` cannot find working-paper series.** NBER (and similar) deposits carry
  an EMPTY container-title, so `--container "NBER Working Papers"` silently returns
  nothing; reach NBER via `--type report` (the script prints this hint on empty
  container-filtered results).
- **Deposits are occasionally wrong or incomplete** — e.g. a major 1995 TAR paper's
  deposit lists only 2 of its 3 authors. `verify` proves a DOI exists and matches a
  title; it does not certify the record's author list or every field. Treat Crossref as
  the best single source, not as infallible ground truth.

Etiquette: the script rate-limits itself and backs off on 429s. Crossref is free and
uncapped for this usage pattern.
