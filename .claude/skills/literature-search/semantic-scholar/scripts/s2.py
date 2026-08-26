#!/usr/bin/env python3
"""Semantic Scholar Graph API client. Stdlib + requests only.

Subcommands:
  search     relevance search (top-1000 window)
  bulk       bulk search with boolean query syntax (+ - | "phrase"), sortable
  paper      fetch one paper by id (DOI:10..., CorpusId:..., SSRN sha, ...)
  match      single closest title match
  citations  papers citing a given paper (optionally with citation contexts)
  refs       papers a given paper cites
  author     search authors, list a matched author's papers
  recommend  papers similar to one or more seed papers
  snippets   full-text snippet search across the corpus

Auth: set S2_API_KEY (free from semanticscholar.org/product/api) for a
dedicated 1 req/s limit; unauthenticated requests share a strict pool.
Compact line format:  DOI | year | venue | authors | title  (cites=N) [flags]
--json for full records.

CAUTION (metadata quality): S2 records for finance/accounting journals are
often degraded — venue/journal empty, publicationDate null, and `year` can be
the working-paper year rather than the journal issue year. Treat S2 output as
discovery + citation-graph data; confirm citation-grade metadata elsewhere.
DOIs may come back uppercased (normalize); an SSRN DOI in S2 may point at an
early draft with a different title than the current SSRN posting.
"""
import argparse, json, os, sys, time

import requests

GRAPH = "https://api.semanticscholar.org/graph/v1"
RECS = "https://api.semanticscholar.org/recommendations/v1"
FIELDS = "externalIds,title,year,publicationDate,venue,journal,publicationTypes,citationCount,authors"
_last = 0.0


class ApiError(RuntimeError):
    pass


def _req(method, url, **kw):
    global _last
    headers = {}
    key = os.environ.get("S2_API_KEY")
    if key:
        headers["x-api-key"] = key
    for attempt in range(6):
        gap = 1.05 - (time.time() - _last)
        if gap > 0:
            time.sleep(gap)
        _last = time.time()
        r = requests.request(method, url, headers=headers, timeout=30, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            # S2 throttle penalties are sticky: back off 2..64s, honoring Retry-After
            wait = 2 ** (attempt + 1)
            ra = r.headers.get("Retry-After")
            if ra and ra.isdigit():
                wait = max(wait, int(ra))
            time.sleep(min(wait, 120))
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    raise ApiError(f"error: Semantic Scholar kept returning {r.status_code}")


def _get(path, params=None, base=GRAPH):
    return _req("GET", f"{base}{path}", params=params or {})


def doi_of(p):
    doi = (p.get("externalIds") or {}).get("DOI") or ""
    return doi.lower() if doi else "(no DOI)"


def is_wp(p):
    doi = doi_of(p)
    if doi.startswith(("10.2139/", "10.3386/", "10.31235/")):
        return True
    venue = (p.get("venue") or "").lower()
    return venue in ("ssrn electronic journal", "social science research network")


def fmt(p, idx=None):
    j = p.get("journal") or {}
    venue = p.get("venue") or j.get("name") or ""
    if j.get("volume"):
        venue += f" {j['volume'].strip()}" + (f":{j['pages'].strip()}" if j.get("pages") else "")
    flags = " [WP]" if is_wp(p) else ""
    if not venue:
        flags += " [venue missing — verify elsewhere]"
    names = [a.get("name", "?").split()[-1] for a in (p.get("authors") or [])]
    authors = ", ".join(names[:6]) + (" et al." if len(names) > 6 else "")
    date = p.get("publicationDate") or p.get("year")
    prefix = f"{idx}. " if idx is not None else ""
    title = " ".join((p.get("title") or "(untitled)").split())
    return f"{prefix}{doi_of(p)} | {date} | {venue} | {authors} | {title} (cites={p.get('citationCount')}){flags}"


def show_list(papers, args, total=None):
    if args.json:
        print(json.dumps(papers, indent=1))
        return
    if total is not None:
        print(f"# ~{total} matches, showing {len(papers)}")
    for i, p in enumerate(papers, 1):
        print(fmt(p, i))


def common_params(args, fields=FIELDS):
    params = {"fields": fields, "limit": args.n}
    if getattr(args, "year", None):
        params["year"] = args.year          # e.g. 2020 or 2018-2024 or 2020-
    if getattr(args, "venue", None):
        params["venue"] = args.venue
    if getattr(args, "min_citations", None):
        params["minCitationCount"] = args.min_citations
    if getattr(args, "pub_types", None):
        params["publicationTypes"] = args.pub_types  # Review,JournalArticle,...
    return params


def cmd_search(args):
    data = _get("/paper/search", {**common_params(args), "query": args.query})
    show_list(data.get("data", []), args, data.get("total"))


def cmd_bulk(args):
    params = {**common_params(args), "query": args.query}
    if args.sort:
        params["sort"] = args.sort          # citationCount:desc | publicationDate:desc
    data = _get("/paper/search/bulk", params)
    show_list((data.get("data") or [])[:args.n], args, data.get("total"))


def cmd_paper(args):
    p = _get(f"/paper/{args.id}", {"fields": FIELDS + ",abstract,tldr,openAccessPdf"})
    if p is None:
        sys.exit(f"{args.id}: not found")
    if args.json:
        print(json.dumps(p, indent=1))
        return
    print(fmt(p))
    tldr = (p.get("tldr") or {}).get("text")
    if tldr:
        print(f"    TLDR: {tldr}")
    if (p.get("openAccessPdf") or {}).get("url"):
        print(f"    OA PDF: {p['openAccessPdf']['url']}")


def cmd_match(args):
    data = _get("/paper/search/match", {"query": args.title, "fields": FIELDS})
    if data is None:
        print("NO title match found")
        return
    if args.json:
        print(json.dumps(data.get("data", []), indent=1))
        return
    for p in data.get("data", []):
        print(f"matchScore={p.get('matchScore'):.1f}  {fmt(p)}")


def _edge_list(args, kind):
    fields = ",".join("citingPaper." + f if kind == "citations" else "citedPaper." + f
                      for f in FIELDS.split(","))
    if kind == "citations" and args.contexts:
        fields += ",contexts,isInfluential"
    key = "citingPaper" if kind == "citations" else "citedPaper"
    if args.by_cites:
        # edges arrive newest-first; page through up to --max-edges, rank by the
        # citing/cited paper's own citation count (offset+limit capped at 9999)
        rows, offset = [], 0
        while offset < min(args.max_edges, 9000):
            try:
                data = _get(f"/paper/{args.id}/{kind}",
                            {"fields": fields, "limit": 1000, "offset": offset})
            except ApiError as e:
                if not rows:
                    raise
                print(f"# WARNING: rate-limited mid-paging ({e}); ranking over the "
                      f"{len(rows)} edges fetched so far — rankings may be incomplete",
                      file=sys.stderr)
                break
            if data is None:
                sys.exit(f"{args.id}: not found")
            batch = data.get("data", [])
            rows.extend(batch)
            if data.get("next") is None or not batch:
                break
            offset = data["next"]
        print(f"# ranked over {len(rows)} {kind} edges", file=sys.stderr)
        rows.sort(key=lambda r: -((r.get(key) or {}).get("citationCount") or 0))
    else:
        # the citations/references endpoints have no server-side minCitationCount:
        # fetch a bigger page when filtering client-side below
        limit = 1000 if getattr(args, "min_citations", None) else args.n
        data = _get(f"/paper/{args.id}/{kind}", {"fields": fields, "limit": limit})
        if data is None:
            sys.exit(f"{args.id}: not found")
        rows = data.get("data", [])
    if getattr(args, "min_citations", None):
        rows = [r for r in rows if ((r.get(key) or {}).get("citationCount") or 0) >= args.min_citations]
    rows = rows[:args.n]
    papers = [(r.get("citingPaper") if kind == "citations" else r.get("citedPaper"), r) for r in rows]
    if args.json:
        print(json.dumps(rows, indent=1))
        return
    for i, (p, r) in enumerate(papers, 1):
        if not p:
            continue
        infl = " [influential]" if r.get("isInfluential") else ""
        print(fmt(p, i) + infl)
        for c in (r.get("contexts") or [])[:2]:
            print(f'     "{c.strip()[:300]}"')


def cmd_citations(args):
    _edge_list(args, "citations")


def cmd_refs(args):
    _edge_list(args, "references")


def cmd_author(args):
    data = _get("/author/search", {"query": args.name, "fields": "name,affiliations,paperCount,citationCount,hIndex"})
    cands = (data or {}).get("data", [])
    if not cands:
        sys.exit("no author match")
    for c in cands[1:3]:
        print(f"# other candidate: {c.get('name')} ({'; '.join(c.get('affiliations') or ['?'])}, {c.get('paperCount')} papers, id={c.get('authorId')})", file=sys.stderr)
    a = cands[0] if not args.author_id else {"authorId": args.author_id, "name": f"authorId {args.author_id}"}
    print(f"# top author match: {a.get('name')} ({a.get('paperCount', '?')} papers, h={a.get('hIndex', '?')})")
    # author/{id}/papers has no server-side year filter: over-fetch and filter here
    limit = max(args.n, 100) if getattr(args, "year", None) else args.n
    papers = _get(f"/author/{a['authorId']}/papers", {"fields": FIELDS, "limit": limit})
    rows = sorted(papers.get("data", []), key=lambda p: -(p.get("year") or 0))
    if getattr(args, "year", None):
        lo, dash, hi = args.year.partition("-")
        lo = int(lo) if lo else None
        hi = int(hi) if hi else (lo if not dash else None)
        rows = [p for p in rows if p.get("year")
                and (lo is None or p["year"] >= lo) and (hi is None or p["year"] <= hi)]
    show_list(rows[:args.n], args)


def cmd_recommend(args):
    body = {"positivePaperIds": args.ids}
    data = _req("POST", f"{RECS}/papers", params={"fields": FIELDS, "limit": args.n}, json=body)
    show_list((data or {}).get("recommendedPapers", []), args)


def cmd_batch(args):
    data = _req("POST", f"{GRAPH}/paper/batch", params={"fields": FIELDS},
                json={"ids": args.ids})
    show_list([p for p in (data or []) if p], args)


def cmd_snippets(args):
    data = _get("/snippet/search", {"query": args.query, "limit": args.n})
    rows = (data or {}).get("data", [])
    ids = []
    for i, s in enumerate(rows, 1):
        sn, paper = s.get("snippet", {}), s.get("paper", {})
        cid = paper.get("corpusId")
        if cid is not None and cid not in ids:
            ids.append(cid)
        print(f"{i}. [{cid}] {paper.get('title')}")
        print(f'   "{(sn.get("text") or "").strip()[:400]}"')
    if args.resolve and ids:
        print("\n# resolved records (one line per unique paper):")
        recs = _req("POST", f"{GRAPH}/paper/batch", params={"fields": FIELDS},
                    json={"ids": [f"CorpusId:{c}" for c in ids]}) or []
        for rec in sorted((r for r in recs if r), key=lambda r: -(r.get("citationCount") or 0)):
            print(fmt(rec))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(p):
        p.add_argument("-n", type=int, default=10, help="max results")
        p.add_argument("--year", help="2020 | 2018-2024 | 2020-")
        p.add_argument("--venue", help="comma-separated venue names")
        p.add_argument("--min-citations", type=int)
        p.add_argument("--pub-types", help="JournalArticle,Review,Conference,...")
        p.add_argument("--json", action="store_true")

    p = sub.add_parser("search", help="relevance search")
    p.add_argument("query"); add_common(p); p.set_defaults(func=cmd_search)

    p = sub.add_parser("bulk", help='boolean search: + required, - excluded, | or, "phrase"')
    p.add_argument("query")
    p.add_argument("--sort", help="citationCount:desc | publicationDate:desc")
    add_common(p); p.set_defaults(func=cmd_bulk)

    p = sub.add_parser("paper", help="one paper by id (DOI:..., CorpusId:..., paperId)")
    p.add_argument("id"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_paper)

    p = sub.add_parser("match", help="closest single title match")
    p.add_argument("title"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_match)

    p = sub.add_parser("citations", help="papers citing this paper (newest first by default)")
    p.add_argument("id"); p.add_argument("--contexts", action="store_true", help="include quoted citation contexts")
    p.add_argument("--by-cites", action="store_true", help="rank citing papers by their own citation count (pages through edges)")
    p.add_argument("--max-edges", type=int, default=3000, help="edge sample size for --by-cites")
    add_common(p); p.set_defaults(func=cmd_citations)

    p = sub.add_parser("refs", help="papers this paper cites")
    p.add_argument("id"); p.add_argument("--by-cites", action="store_true")
    p.add_argument("--max-edges", type=int, default=3000)
    add_common(p); p.set_defaults(func=cmd_refs)

    p = sub.add_parser("author", help="author search + their papers (newest first)")
    p.add_argument("name"); p.add_argument("--author-id", help="skip search, use this id")
    add_common(p); p.set_defaults(func=cmd_author)

    p = sub.add_parser("recommend", help="similar papers from seed ids")
    p.add_argument("ids", nargs="+"); add_common(p); p.set_defaults(func=cmd_recommend)

    p = sub.add_parser("batch", help="fetch up to 500 papers in one call (ids: DOI:..., CorpusId:..., paperId)")
    p.add_argument("ids", nargs="+"); p.add_argument("--json", action="store_true")
    p.add_argument("-n", type=int, default=500, help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser("snippets", help="full-text snippet search")
    p.add_argument("query"); p.add_argument("-n", type=int, default=5)
    p.add_argument("--resolve", action="store_true",
                   help="batch-fetch full records for the hit papers (citable fields, sorted by citations)")
    p.set_defaults(func=cmd_snippets)

    args = ap.parse_args()
    try:
        args.func(args)
    except ApiError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
