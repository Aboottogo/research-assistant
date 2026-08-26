# OpenAlex — topical discovery, citation graph, and author search

OpenAlex indexes ~250M works with good relevance ranking, clean preprint typing, and a
full citation graph. It is the best free engine for **finding papers by topic**, walking
**cited-by/references**, and listing **an author's or a journal's output**. Its known weak
spot is the *year*: see Landmines.

## Tool

`scripts/openalex.py` (python3 + requests; no key needed).

```
python3 scripts/openalex.py <subcommand>

search "recognition versus disclosure pension" -n 10 [--type article] [--cited]
       [--source 0304-405X | --source "Journal of Finance"] [--from-year 2018] [--to-year 2026]
filter --title "five-factor" --type article --source 0304-405X [--raw 'is_oa:true'] [--cited]
doi 10.2308/accr-50381 [more DOIs...]           # record(s) by DOI; batched in one call
cited-by 10.1016/j.jacceco.2004.06.003 -n 10    # citing papers, most-cited first
refs 10.2308/tar-2019-1066 -n 20                # what the paper cites
author "Katherine Schipper" -n 15 [--recent]    # works, most-cited (or newest) first
published "Economic Consequences of Operating Lease Recognition"   # WP title -> article version
```

Output line: `DOI | year | venue vol(iss):pages | authors | title (cites=N)`; preprints
flagged `[WP]`. `--json` for full records. `--cited` sorts a filtered/search set by
citation count — useful within a well-filtered set (a source, an author, a `cited-by`
listing); on a broad full-corpus `search` it degrades into globally famous papers with
incidental term matches.

## Quota

Anonymous access is credit-metered (~1000 credits per ~2h window). Any text-search call
costs 10 credits — `search`, and also `filter` with `--title` or a `--raw` `.search:`
filter. Pure equality filters (`--type`/`--source`/year, batched `doi`, `cited-by`,
author-ID) cost 1; single-work fetches cost 0. The script prints `[credits remaining …]`
to stderr after each call. Practical upshot: text searches of any kind are the expensive
calls; ID and equality filters are nearly free. If you hit 429s with credits exhausted,
wait for the window to reset or continue in another tool.

## Landmines

- **The year can be wrong for citation purposes.** `publication_year`/`publication_date`
  is the earliest date OpenAlex knows — frequently the online-first date. Example: the
  Fama-French five-factor paper (JFE 116(1), 2015) carries `publication_year: 2014`;
  Yu's TAR 88(3) 2013 paper carries 2012. Volume/issue/pages are reliable; the printed
  year is not. Before a year goes into a citation, confirm it against the journal
  issue/publisher record rather than trusting this field.
- **Preprint and published are separate works.** An SSRN working paper and its journal
  version are two records, each with its own DOI and its own citation count. The split
  can be extreme — a Journal of Finance article can show cited_by_count 0 while its SSRN
  twin holds the citations — so never rank or judge importance by cited_by_count alone
  for papers that circulated as working papers; check the twin. Search results can
  contain both records — dedupe by title, keep the `type: article` one, and report the
  `[WP]` one only as provenance.
  `published` automates the WP→article direction; verify the match by title/authors.
- **SSRN versioning.** `type: preprint` + source "SSRN Electronic Journal" marks SSRN
  records; OpenAlex may label them `acceptedVersion` regardless of actual status.
- **Author disambiguation is algorithmic.** `author` prints runner-up candidates on
  stderr; if the works list looks off (wrong field, wrong era), the match is probably a
  namesake — retry with the more specific name form or check the candidates. Clustered
  author entities sometimes carry a wrong expanded name (e.g. "Jürgen" for J. Rauh); the
  script prints each work's own byline (`raw_author_name`), which avoids that, but full
  first names may still need publisher confirmation. One person can also be SPLIT across
  several author records — when completeness matters (a full bibliography), supplement
  `author` with `filter --raw 'raw_author_name.search:LASTNAME FIRSTNAME'` to sweep the
  corpus by byline.
- **Journal filter by ISSN beats by name** (`--source 0304-405X`): name search can match
  lookalike venues.
- **Full-text search answers "who uses X" questions.** `search` covers title, abstract,
  AND indexed full text, and `filter --raw 'fulltext.search:"exact phrase"'` restricts
  to full-text matches — the way to find papers by their data sections (a database name,
  a method, an instrument) that never surfaces in titles/abstracts. ALWAYS quote the
  phrase: unquoted multi-word full-text queries degenerate into loose AND noise.
  Coverage is partial (indexed OA texts), so treat the result set as a floor.
- **Generic query words drown in the cross-discipline corpus.** `search` matches over
  all fields of 250M works: a query like "securities class action disclosure" returns
  network-security and medical papers above the finance literature. Anchor queries with
  a distinctive phrase ("post-earnings announcement drift"), or add `--source`/`--type`/
  year filters, or use `filter --title` with the words that would appear in a title.
