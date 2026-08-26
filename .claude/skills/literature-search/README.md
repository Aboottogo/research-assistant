# literature-search

A Claude Code skill for searching academic literature across five databases — CrossRef, OpenAlex, Semantic Scholar, Consensus, and Scite — tuned for finance/accounting research. It finds papers, verifies and completes citations, checks claims against citation evidence, chases citations, and resolves working papers to their published versions. Every delivered reference carries a resolvable full-text locator (DOI preferred), ready to add to Zotero.

This repo supersedes the older Agents365 `semanticscholar-skill`.

## Layout

```
SKILL.md               the orchestration layer: database choice, output contract, quotas
crossref/              bibliographic lookup, verification, WP→published resolution (script)
openalex/              topical discovery, citation graph, author search (script)
semantic-scholar/      citation contexts, recommendations, full-text snippets (script)
consensus/             evidence-oriented topical search (MCP tool, doc only)
scite/                 citation-grade records + smart-citation tallies (MCP tool, doc only)
```

Each subdirectory is self-contained — its `.md` doc plus (for the REST databases) a `scripts/` client — and is usable standalone without the rest of the repo.

## Prerequisites

- python3 with `requests` (the three scripts have no other dependencies)
- `S2_API_KEY` in the environment — free from semanticscholar.org/product/api (without it, Semantic Scholar throttles hard)
- The Consensus and Scite MCP connectors installed and connected (no public REST fallback for either)
- An email address to pass to CrossRef's polite pool via `--mailto`

Note: the OpenAlex credit window (~1000 per 2h) is shared across every session on your network identity — two concurrent search-heavy sessions can starve each other into 429s.

Missing pieces degrade gracefully: without the MCP connectors you lose Consensus/Scite but the three script databases still work.

## Install

Use the repo root as the skill directory (e.g. clone into `~/.claude/skills/literature-search/`). The skill only activates when invoked explicitly with `/literature-search` — it never triggers on its own.

## Searching in a subagent

By default the agent searches in your conversation, keeping intermediate results available — useful when one answer motivates your next question (in testing, a known-item lookup dropped to a single call because an earlier topical sweep had already surfaced the paper).

The cost is context: in testing, a single multi-database search consumed roughly 45k tokens (known-item lookup) to 185k (broad sweep with law-review chasing) of the conversation window. If you expect to ask several questions, or want the chat kept lean for a long session, ask for delegation explicitly — e.g. "use a subagent for the searches." Each search then runs in an isolated agent and returns only the compact reference list and findings (~3-6k tokens), which is all that later questions and an end-of-chat "add these to Zotero" need. Delegate when the session will be long or the sweep broad; stay inline for a quick question or when you want to steer the search as it happens.

## Scope notes

- Legal scholarship (law reviews) is structurally underweighted in all five databases: often discoverable but without a resolvable locator. The skill flags such items as unverifiable rather than dropping them silently; chase them in HeinOnline/Westlaw.
- Retraction checking is out of scope (Scite surfaces `editorialNotices` when records are fetched, but the skill does not sweep for retractions).
- Finding full-text PDFs and interacting with Zotero are out of scope; the skill's job ends at verified, locator-carrying references.
