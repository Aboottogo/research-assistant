# Consensus — evidence-oriented topical search (MCP tool)

Requires the Consensus MCP connector to be installed and connected; there is no public
REST fallback. The `mcp__consensus__search` tool searches ~200M papers and returns, per result: title,
authors (often truncated to "X et al."), year, journal name, citation count, DOI, and the
full abstract. Its strength is **claim-oriented topical discovery** — "what does the
evidence say about X" — where the returned abstracts let you weigh findings directly.
It is not a bibliographic authority: several returned fields need care before they go
into a citation (see below).

## Using it well

- One focused query usually returns 20 abstract-rich results (~10k tokens). **2-4
  distinct queries cover most questions**; batch at most 3 calls per turn. Broad
  fishing expeditions get expensive fast, and accounts can be usage-metered — if the
  tool result carries a sign-up/usage/upgrade message, it must be repeated verbatim
  in your response.
- There is no result-count parameter and no pagination on free accounts. Vary the
  query, not the page.
- Filters (`year_min`, `study_types`, `exclude_preprints`, …) only when the user's
  request implies them. `exclude_preprints` is NOT reliable for finance/economics:
  SSRN records survive it.

## Reading the results (the landmines)

- **The DOI may be the working paper's, even when a journal name is shown.** Famous
  finance/accounting papers frequently come back as e.g. "Journal of Finance …
  DOI: 10.2139/ssrn.354387". A DOI starting `10.2139/` (SSRN) or `10.3386/` (NBER) is a
  working-paper DOI regardless of the journal label: label the reference "[working
  paper DOI]", and do not present that DOI as the published article's. Consensus alone
  cannot supply the journal-version DOI.
- **The year can be the online-first/draft year**, not the citable issue year (the JFE
  2015 five-factor paper is listed as 2014). When the year matters, corroborate it —
  e.g., how citing papers in the same results refer to it ("Fama and French (2015)").
- **No volume/issue/pages are returned.** Do not invent them; deliver the citation
  without them or mark them unverified.
- **Author lists are truncated.** "E. Fama et al." is not a complete author string;
  say so rather than guessing the coauthors.
- **A returned DOI can belong to a reprint anthology, not the article** — e.g. a
  canonical 1995 TAR paper returned only a Wiley book-chapter DOI (10.1002/…ch4). If
  the DOI's publisher prefix doesn't match the claimed journal, label the DOI as
  provenance-uncertain rather than presenting it as the article's.
- **Secondary-content lookalikes** (CFA Digest summaries, comments, discussions) rank
  well and can carry big citation counts; check that a hit is the primary paper before
  citing it.
- **Some journal strings are systematically corrupted** (shared with other indexes):
  Auditing: A Journal of Practice & Theory papers (DOI prefix `10.2308/aud`) show the
  journal "Ear and Hearing". An absurd journal for the topic means a corrupted field,
  not a different paper.
- Journal field may read "Unknown Journal" even for major published articles; treat as
  missing, not as evidence the paper is unpublished.

Deliverable discipline: for every reference, report what the tool actually returned,
flag `[working paper]` where the markers above fire, and clearly separate tool-verified
fields from anything you added from your own knowledge.
