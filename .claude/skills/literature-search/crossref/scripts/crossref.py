#!/usr/bin/env python3
"""Crossref REST API client for literature search. Stdlib + requests only.

Subcommands:
  search    relevance search over bibliographic metadata
  doi       fetch full canonical records for one or more DOIs
  published find the published journal-article version of a working paper title
  verify    check DOI<->title pairs (catches hallucinated or mismatched citations)

Compact output line format:
  DOI | year | container (vol(iss):pages) | authors | title      [flags]
Working papers / preprints are flagged [WP]. Use --json for full records.
"""
import argparse, json, re, sys, time, unicodedata

import requests

API = "https://api.crossref.org/works"
MAILTO = "literature-search-skill@example.org"  # any contact address; override with --mailto
_SELECT = ("DOI,type,title,container-title,author,issued,published-print,"
           "published-online,volume,issue,page,publisher,relation,group-title,score")
_last_call = 0.0


def _get(url, params):
    """Polite GET: mailto param, min gap, honor 429/5xx with backoff."""
    global _last_call
    for attempt in range(4):
        gap = 0.2 - (time.time() - _last_call)
        if gap > 0:
            time.sleep(gap)
        _last_call = time.time()
        r = requests.get(url, params=params, timeout=30,
                         headers={"User-Agent": f"literature-search-skill (mailto:{params.get('mailto', MAILTO)})"})
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    sys.exit(f"error: Crossref kept returning {r.status_code}")


# ---------- record helpers ----------

WP_PREFIXES = ("10.2139/", "10.3386/")           # SSRN, NBER
WP_CONTAINERS = ("ssrn electronic journal",)

def is_wp(msg):
    """Working-paper heuristic. Crossref types alone are not enough: some SSRN
    records are typed journal-article with container 'SSRN Electronic Journal'."""
    if msg.get("type") in ("posted-content", "report"):
        return True
    doi = (msg.get("DOI") or "").lower()
    if doi.startswith(WP_PREFIXES):
        return True
    ct = [c.lower() for c in msg.get("container-title", [])]
    return any(c in WP_CONTAINERS for c in ct)


def citable_date(msg):
    """(year, 'YYYY[-MM[-DD]]'). published-print is the citable issue date when
    present; 'issued' is the earliest known date and can be the online-first
    year (e.g. a Jan-2024 issue article issued 2023-12). Never use 'created'."""
    for field in ("published-print", "issued"):
        parts = (msg.get(field) or {}).get("date-parts", [[None]])[0]
        if parts and parts[0]:
            return parts[0], "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(parts))
    return None, ""


def fmt_authors(msg, n=6):
    names = [a.get("family") or a.get("name", "?") for a in msg.get("author", [])]
    return ", ".join(names[:n]) + (" et al." if len(names) > n else "")


def fmt_line(msg, idx=None):
    year, _ = citable_date(msg)
    title = " ".join((msg.get("title") or ["(untitled)"])[0].split())
    ct = (msg.get("container-title") or [""])[0]
    if is_wp(msg):
        inst = msg.get("institution")
        inst_name = inst[0].get("name", "") if isinstance(inst, list) and inst else ""
        src = msg.get("group-title") or inst_name
        venue = f"[WP] {src or ct or msg.get('type')}"
    else:
        venue = ct
        vol, iss, pg = msg.get("volume"), msg.get("issue"), msg.get("page")
        if vol:
            venue += f" {vol}" + (f"({iss})" if iss else "") + (f":{pg}" if pg else "")
    prefix = f"{idx}. " if idx is not None else ""
    return f"{prefix}{msg.get('DOI','?')} | {year} | {venue} | {fmt_authors(msg)} | {title}"


def norm_title(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return re.sub(r"[^a-z0-9 ]+", " ", t).split()


def title_sim(a, b):
    """Token Jaccard similarity of two titles."""
    A, B = set(norm_title(a)), set(norm_title(b))
    return len(A & B) / max(1, len(A | B))


# ---------- subcommands ----------

def cmd_search(args):
    params = {"query.bibliographic": args.query, "rows": args.rows, "select": _SELECT,
              "mailto": args.mailto}
    filters = []
    if args.type:
        filters.append(f"type:{args.type}")
    if args.from_year:
        filters.append(f"from-pub-date:{args.from_year}-01-01")
    if args.until_year:
        filters.append(f"until-pub-date:{args.until_year}-12-31")
    if args.container:
        filters.append(f"container-title:{args.container}")
    if filters:
        params["filter"] = ",".join(filters)
    if args.author:
        params["query.author"] = args.author
    data = _get(API, params)
    items = data["message"]["items"]
    if args.json:
        print(json.dumps(items, indent=1))
        return
    print(f"# {data['message']['total-results']} matches, showing {len(items)}")
    if not items and args.container:
        print("# hint: container-title filters on publisher-deposited strings; working-paper"
              "\n# series (e.g. NBER) often deposit an EMPTY container — try --type report,"
              "\n# or drop --container and filter by eye.")
    for i, m in enumerate(items, 1):
        print(fmt_line(m, i))


def cmd_doi(args):
    for doi in args.dois:
        data = _get(f"{API}/{doi}", {"mailto": args.mailto})
        if data is None:
            print(f"{doi} | NOT FOUND in Crossref")
            continue
        m = data["message"]
        if args.json:
            print(json.dumps(m, indent=1))
        else:
            print(fmt_line(m))
            _, full = citable_date(m)
            pp = (m.get("published-print") or {}).get("date-parts")
            po = (m.get("published-online") or {}).get("date-parts")
            print(f"    dates: citable={full}"
                  + (f" print={pp[0]}" if pp else "") + (f" online={po[0]}" if po else ""))
            rel = m.get("relation") or {}
            for k in ("is-preprint-of", "has-preprint"):
                for r in rel.get(k, []):
                    print(f"    relation {k}: {r.get('id')}")


def cmd_published(args):
    """Find the published journal-article version of a (working paper) title."""
    params = {"query.bibliographic": args.title, "rows": 8, "select": _SELECT,
              "filter": "type:journal-article", "mailto": args.mailto}
    if args.author:
        params["query.author"] = args.author
    items = _get(API, params)["message"]["items"]
    cands = [(title_sim(args.title, (m.get("title") or [""])[0]), m) for m in items]
    cands = [(s, m) for s, m in cands if s >= 0.5 and not is_wp(m)]
    if not cands:
        print("NO published journal-article match found (title similarity >= 0.5).")
        print("The work may be unpublished, or published under a changed title — retry with distinctive title words plus --author.")
        return
    cands.sort(key=lambda x: -x[0])
    for s, m in cands[:args.rows]:
        print(f"sim={s:.2f}  {fmt_line(m)}")


def cmd_verify(args):
    """PAIRS: 'doi :: expected title' lines from args or stdin."""
    pairs = args.pairs or [l.strip() for l in sys.stdin if l.strip()]
    ok = True
    for p in pairs:
        if "::" not in p:
            print(f"SKIP (need 'doi :: title'): {p}")
            continue
        doi, title = [x.strip() for x in p.split("::", 1)]
        data = _get(f"{API}/{doi}", {"mailto": args.mailto})
        if data is None:
            print(f"FAIL  {doi}  — DOI does not exist in Crossref")
            ok = False
            continue
        m = data["message"]
        real = (m.get("title") or [""])[0]
        s = title_sim(title, real)
        if s >= 0.6:
            print(f"OK    {doi}  sim={s:.2f}  {fmt_line(m)}")
        else:
            print(f"FAIL  {doi}  sim={s:.2f}  registered title: {real}")
            ok = False
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mailto", default=MAILTO, help="contact email for Crossref polite pool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="relevance search")
    p.add_argument("query")
    p.add_argument("--rows", type=int, default=10)
    p.add_argument("--type", help="e.g. journal-article (excludes most working papers)")
    p.add_argument("--container", help="journal name filter, e.g. 'Journal of Finance'")
    p.add_argument("--author")
    p.add_argument("--from-year", type=int)
    p.add_argument("--until-year", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("doi", help="fetch records by DOI")
    p.add_argument("dois", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doi)

    p = sub.add_parser("published", help="published version of a working-paper title")
    p.add_argument("title")
    p.add_argument("--author")
    p.add_argument("--rows", type=int, default=3)
    p.set_defaults(func=cmd_published)

    p = sub.add_parser("verify", help="verify 'doi :: title' pairs (args or stdin)")
    p.add_argument("pairs", nargs="*")
    p.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
