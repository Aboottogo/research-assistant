# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A research-assistant workspace for academic (finance/accounting) research — not a software project. There is no build, lint, or test system, and it is not a git repository. The substance lives in `.claude/skills/` and the connected MCP servers (Zotero, Scite, Consensus); sessions here are about literature search, citation verification, and Zotero library management.

## Skills — read before acting

- **`.claude/skills/literature-search/SKILL.md`** — orchestrates five databases (CrossRef, OpenAlex, Semantic Scholar via scripts; Consensus, Scite via MCP). Invoke-only (`/literature-search`); it never self-triggers. Before first using a database in a session, read its `<db>/<db>.md` doc — each carries calling conventions and known landmines.
- **`.claude/skills/zotero/SKILL.md`** — routes Zotero work between the `mcp__zotero__*` MCP tools and the `zot` CLI. Default to MCP for reads/adds; use `zot` for workspace RAG search, PDF fetching, duplicates, and bulk/previewable mutations. The `zotero-cli-cc` skill holds full `zot` syntax.

## Binding rules from those skills

**Literature-search output contract:** every delivered reference needs authors, citable year, title, venue, and a resolvable locator (DOI preferred). Verify all DOIs with `crossref/scripts/crossref.py verify "DOI :: title"` before delivery; report locator-less items as unverifiable rather than dropping them. CrossRef is the referee for citable years, venues, and full author names — other databases serve online-first years, corrupted venues, and truncated authors. SSRN (`10.2139/`) and NBER (`10.3386/`) DOIs are working-paper DOIs regardless of displayed journal; resolve to the published version with `crossref.py published` or `openalex.py published`.

**Quotas:** Consensus ≤3 calls/turn (metered; repeat any usage/upgrade message verbatim). OpenAlex ~1000 credits/2h shared across sessions (text searches cost 10, equality filters 1, GETs 0). S2 needs `S2_API_KEY` and max 1 request/s — never parallelize s2.py calls. 

**Zotero index maintenance (silent-failure risk):** after adding items run `zotero-mcp update-db` (CLI, not the MCP tool). After any delete or merge run `zotero-sync-deletions`, then tell the user to restart Claude Code so the MCP server drops its cached index. A "Could not fetch full item data" / 404 in semantic-search output means the deletion sync is overdue. Remembering this is Claude's job, not the user's.

## Common commands

```bash
# Literature search scripts (python3 + requests; run from the skill dir)
python3 .claude/skills/literature-search/crossref/scripts/crossref.py verify "DOI :: title"
python3 .claude/skills/literature-search/crossref/scripts/crossref.py published "title"
python3 .claude/skills/literature-search/openalex/scripts/openalex.py author "Name"
python3 .claude/skills/literature-search/semantic-scholar/scripts/s2.py citations DOI --by-cites --contexts

# Zotero
zot workspace query "question" --workspace NAME   # RAG search
zot ask "question" --workspace NAME               # citation-keyed evidence pack
zot find-pdf KEY                                  # fetch missing/paywalled PDF (needs Zotero desktop)
zot --json duplicates
zotero-mcp update-db                              # after adds
zotero-sync-deletions [--dry-run]                 # after deletes/merges
```

## Context management for searches

A multi-database search consumes ~45k–185k tokens inline. For long sessions or broad sweeps, delegate searches to a subagent (returns ~3–6k tokens of compact references); stay inline for quick questions or when the user wants to steer the search.
