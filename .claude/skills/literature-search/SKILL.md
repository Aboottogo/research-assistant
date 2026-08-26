---
name: literature-search
description: Search academic literature across CrossRef, OpenAlex, Semantic Scholar, Consensus, and Scite — find papers, verify and complete citations, check claims, chase citations, resolve working papers to published versions. Tuned for finance/accounting.
disable-model-invocation: true
---

# literature-search

Five databases, each self-contained in a subdirectory of this skill with its own doc and, for the REST ones, a script. **Read a database's `<db>/<db>.md` before first using that database in a session** — each doc carries its calling conventions and known landmines. Scripts need python3 + requests; Consensus and Scite are MCP tools.

## Choosing databases

No single database answers every question; expect to combine two or three. What each is best at:

| Need | Use |
|---|---|
| What the evidence says (findings, abstracts) | Consensus; Scite (full-text snippets). OpenAlex/S2/CrossRef carry no abstracts for most paywalled finance/accounting journals — they identify papers, they can't report findings |
| Known-item lookup, exact citation, citable dates | CrossRef (authoritative); Scite (complete vol/issue/pages) |
| Topical discovery, mapping a field | OpenAlex; S2 `bulk` citation-sorted. A recent survey's reference list (`refs`) is often the cheapest map of a field |
| Who cites X, ranked; how citers use it | OpenAlex `cited-by`; S2 `citations --by-cites --contexts` (contexts quote the citing sentences; may 429 on papers with 2000+ citations). Scite's MCP tool cannot list incoming citations — only counts |
| Claim adjudication | Scite tallies + snippets, but its classifier under-detects disagreement: contrasting counts mean something only when nonzero. S2 citation contexts are the cross-check |
| Working paper → published version | `crossref.py published` or `openalex.py published` |
| An author's works | OpenAlex `author` — and check its stderr runner-up candidates: in every database tested, a bare author name can top-match a namesake in another field |
| NBER working papers | OpenAlex only; Consensus, Scite, and S2 don't reach NBER |
| Seminal-work identification | Never a topical query — every database buries seminal papers under derivative work. Come in with a candidate title, or citation-count-sort within a filtered set |

## Output contract (binding)

Every delivered reference: authors, citable year, title, venue, and a resolvable full-text locator — DOI preferred; else an open-access PDF URL; else a publisher/repository URL confirmed live (aggregator pages don't count); a PMID may ride along but never substitutes for the locator. Label working papers "[working paper]"; prefer the published version. An on-topic item with no resolvable locator is reported as unverifiable, not delivered as a citation and not silently dropped.

Before delivery: run every DOI through `crossref/scripts/crossref.py verify "DOI :: title" ...` — it catches hallucinated DOIs and DOI-title mismatches. Fetch each non-DOI locator once to confirm it resolves.

## Cross-database verification — the step single-database answers get wrong

- **Years.** Every database except CrossRef serves online-first or draft years for finance/accounting journals. When volume+journal imply a different year than the record, the issue year is the citable one; CrossRef's `citable=` line is the referee.
- **Working-paper DOIs behind journal labels.** A `10.2139/` (SSRN) or `10.3386/` (NBER) DOI is a working-paper DOI regardless of the journal name displayed with it (common in Consensus and S2). Resolve to the journal DOI with `published`; titles often change on publication, so on a miss retry with distinctive title words plus author.
- **Split records.** A working paper and its journal version are separate records with split citation counts in every database; dedupe by title and deliver the published record.
- **Authors.** Truncated, reordered, misattributed, or missing across Consensus/S2/Scite; CrossRef `doi` returns the deposited full names. Rarely the deposit itself is incomplete — then flag the gap rather than filling it from memory.
- **Venues.** Aggregator metadata corrupts some journals wholesale (every `10.2308/aud` DOI shows venue "Ear and Hearing" in S2 and Consensus). Trust CrossRef for venue strings.

## Quotas

- **Consensus: metered account.** At most 3 calls per turn; if a tool result carries a usage/sign-up/upgrade message, repeat it verbatim to the user.
- **OpenAlex: ~1000 credits per 2h window.** Text searches (`search`, `filter --title`, `.search:` raw filters) cost 10 credits; equality filters 1; single-record GETs 0.
- CrossRef and S2 (with `S2_API_KEY`) are uncapped for this usage; S2 allows 1 request/s — never run s2.py invocations in parallel.
