---
name: zotero
description: Route Zotero work between the zotero-mcp MCP tools and the zot CLI, and run the index maintenance that keeps semantic search correct. Use when adding, deleting, merging, searching, or reading Zotero items, when a library PDF is missing, or when choosing between the MCP tools and the zot command line.
---

# Zotero: two providers, one library

`zotero-mcp` (MCP tools, `mcp__zotero__*`) and the `zot` CLI both reach the same
Zotero library. Route by capability, not by whichever is closer to hand — the
MCP tool names are always pre-loaded, so there is a standing pull toward them
that is about reachability, not fitness.

For `zot` command syntax, the `zotero-cli-cc` skill holds the full reference.
This skill decides *which* provider to use; that one documents *how* to drive
the CLI.

## Default to the MCP tools

Reads, metadata, annotations, and adds. Richer schemas, no shell round-trip.
`zotero_add_item` in particular beats `zot add`: it validates collections before
creating anything, and `if_exists='file'` makes re-adds idempotent.

## Use the `zot` CLI for

| Task | Command |
|------|---------|
| Workspace RAG search | `zot workspace query "q" --workspace NAME` |
| Citation-keyed evidence pack | `zot ask "question" --workspace NAME` |
| Fetch a missing/paywalled PDF | `zot find-pdf KEY` (needs Zotero desktop + bridge) |
| Find duplicates | `zot --json duplicates` |
| Rename attachment files | `zot rename KEY --dry-run` |
| Journal metrics | `zot enrich KEY --set "JCR=Q1"` |

Also prefer the CLI for bulk writes and any mutation worth previewing with
`--dry-run` first. None of the above have MCP equivalents.

## Index maintenance — do not skip

These fail *silently*: a stale semantic index returns confident, wrong results.
An orphaned chunk keeps its embedding, so it can **outrank the live copy** of
the same paper in `zotero_semantic_search` — the only tell is a 404 when the
tool tries to fetch the item. Treat any "Could not fetch full item data" in
search output as a signal to run the deletion sync below.

- **After adding items:** run `zotero-mcp update-db`.
  Use the CLI, not the `zotero_update_search_database` MCP tool.
- **After any delete or merge:** run `zotero-sync-deletions`, then tell the user
  to restart Claude Code so the running MCP server drops its cached index.
  Safe to run blindly — it no-ops when already in sync, and refuses to act if
  Zotero reports an empty library. Use `--dry-run` to report without changing.

Remembering this is your job, not the user's.

## Known gaps

- Area/rectangle annotations are unreachable from Claude Code (zotero-mcp issue
  459). Highlights work. Don't promise area-annotation output.
- Check `ZOTERO_MCP_TOOLSETS` before assuming a tool exists. Groups not listed
  there are unregistered — `discovery` (`find_related_papers`,
  `library_coverage`) is off in the current setup.
