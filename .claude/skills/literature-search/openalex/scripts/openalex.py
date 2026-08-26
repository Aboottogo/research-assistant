#!/usr/bin/env python3
"""OpenAlex API client for literature search. Stdlib + requests only.

Subcommands:
  search    relevance search (10 credits/call — the expensive one)
  filter    filtered listing without a text query (1 credit)
  doi       fetch records for one or more DOIs (free for one, 1 credit batched)
  cited-by  papers citing a given DOI (1 credit)
  refs      papers a given DOI cites (1-2 credits)
  author    an author's works (2 credits)
  published find the published-article version of a working-paper title (10 credits)

Anonymous quota: ~1000 credits per ~2h window. Remaining credits print to stderr.
Compact line format:  DOI | year | venue | authors | title  [WP flag] (cites=N)
Working papers/preprints flagged [WP]. --json for full records.

CAUTION (dates): OpenAlex publication_date/publication_year is the EARLIEST
known date, often the online-first date — it can precede the citable issue
year (e.g. J. Fin. Econ. 116(1) 2015 article carries publication_year 2014).
Volume/issue/pages in `biblio` are correct; the year needs independent
confirmation before it goes into a citation.
"""
import argparse, json, re, sys, time

import requests

API = "https://api.openalex.org"
SELECT = "doi,title,display_name,type,publication_year,publication_date,primary_location,biblio,authorships,cited_by_count,ids"
_last = 0.0


def _get(path, params=None):
    global _last
    params = dict(params or {})
    for attempt in range(4):
        gap = 0.12 - (time.time() - _last)
        if gap > 0:
            time.sleep(gap)
        _last = time.time()
        r = requests.get(f"{API}{path}", params=params, timeout=30)
        if r.status_code in (429, 500, 502, 503):
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        rem = r.headers.get("x-ratelimit-remaining")
        if rem is not None:
            print(f"[credits remaining this window: {rem}]", file=sys.stderr)
        return r.json()
    sys.exit(f"error: OpenAlex kept returning {r.status_code}")


def is_wp(w):
    if w.get("type") in ("preprint", "report"):
        return True
    doi = (w.get("doi") or "").replace("https://doi.org/", "")
    if doi.startswith(("10.2139/", "10.3386/")):
        return True
    src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
    return src.lower() in ("ssrn electronic journal", "ssrn", "research papers in economics",
                           "national bureau of economic research")


def fmt(w, idx=None):
    doi = (w.get("doi") or "").replace("https://doi.org/", "") or "(no DOI)"
    year = w.get("publication_year")
    loc = (w.get("primary_location") or {})
    src = (loc.get("source") or {}).get("display_name") or ""
    b = w.get("biblio") or {}
    if is_wp(w):
        venue = f"[WP] {src or w.get('type')}"
    else:
        venue = src
        if b.get("volume"):
            venue += f" {b['volume']}" + (f"({b['issue']})" if b.get("issue") else "")
            if b.get("first_page"):
                venue += f":{b['first_page']}" + (f"-{b['last_page']}" if b.get("last_page") else "")
    names = [(a.get("raw_author_name") or a.get("author", {}).get("display_name") or "?").split()[-1]
             for a in (w.get("authorships") or [])]
    authors = ", ".join(names[:6]) + (" et al." if len(names) > 6 else "")
    title = " ".join((w.get("display_name") or w.get("title") or "(untitled)").split())
    prefix = f"{idx}. " if idx is not None else ""
    return f"{prefix}{doi} | {year} | {venue} | {authors} | {title} (cites={w.get('cited_by_count')})"


def show(data, args, header=True):
    if data is None:
        sys.exit("not found")
    results = data.get("results", [data])
    if args.json:
        print(json.dumps(results, indent=1))
        return
    if header and "meta" in data:
        print(f"# {data['meta']['count']} matches, showing {len(results)}")
    for i, w in enumerate(results, 1):
        print(fmt(w, i))


def common_filters(args):
    f = []
    if getattr(args, "type", None):
        f.append(f"type:{args.type}")
    if getattr(args, "from_year", None):
        f.append(f"from_publication_date:{args.from_year}-01-01")
    if getattr(args, "to_year", None):
        f.append(f"to_publication_date:{args.to_year}-12-31")
    if getattr(args, "source", None):
        # accepts an ISSN (exact) or a source name (resolved to a source id first)
        if any(c.isdigit() for c in args.source):
            f.append(f"primary_location.source.issn:{args.source}")
        else:
            src = _get("/sources", {"search": args.source, "per-page": 2,
                                    "select": "id,display_name,works_count"})
            results = (src or {}).get("results", [])
            if not results:
                sys.exit(f"no OpenAlex source matches name '{args.source}' — try its ISSN")
            top = results[0]
            print(f"# source resolved: {top['display_name']} ({top['id']})", file=sys.stderr)
            f.append(f"primary_location.source.id:{top['id'].rsplit('/', 1)[-1]}")
    return f


def _clean(q):
    """OpenAlex 400s on '?' and similar reserved punctuation in search strings.
    Keep quotes (phrase search), apostrophes, commas, hyphens; strip the rest."""
    return re.sub(r"""[^\w\s\-"',]""", " ", q).strip()


def _title_sim(a, b):
    A = set(re.sub(r"[^a-z0-9 ]+", " ", a.lower()).split())
    B = set(re.sub(r"[^a-z0-9 ]+", " ", b.lower()).split())
    return len(A & B) / max(1, len(A | B))


def cmd_search(args):
    params = {"search": _clean(args.query), "per-page": args.n, "select": SELECT}
    f = common_filters(args)
    if f:
        params["filter"] = ",".join(f)
    if args.cited:
        params["sort"] = "cited_by_count:desc"
    show(_get("/works", params), args)


def cmd_filter(args):
    f = common_filters(args)
    if args.title:
        f.append(f"title.search:{args.title}")
    if args.raw:
        f.append(args.raw)
    if not f:
        sys.exit("filter: need --title, --type, --source, --from-year/--to-year, or --raw")
    params = {"filter": ",".join(f), "per-page": args.n, "select": SELECT}
    if args.cited:
        params["sort"] = "cited_by_count:desc"
    show(_get("/works", params), args)


def cmd_doi(args):
    if len(args.dois) == 1:
        w = _get(f"/works/doi:{args.dois[0]}")
        if w is None:
            print(f"{args.dois[0]} | NOT FOUND in OpenAlex")
            return
        print(fmt(w))
        if args.json:
            print(json.dumps(w, indent=1))
        return
    dois = "|".join(args.dois)
    show(_get("/works", {"filter": f"doi:{dois}", "per-page": len(args.dois), "select": SELECT}), args)


def _oaid(doi):
    w = _get(f"/works/doi:{doi}")  # free call
    if w is None:
        sys.exit(f"DOI {doi} not found in OpenAlex")
    return w["id"].rsplit("/", 1)[-1], w


def cmd_cited_by(args):
    wid, w = _oaid(args.doi)
    print(f"# papers citing: {fmt(w)}")
    params = {"filter": f"cites:{wid}", "per-page": args.n, "select": SELECT,
              "sort": "cited_by_count:desc"}
    show(_get("/works", params), args)


def cmd_refs(args):
    wid, w = _oaid(args.doi)
    full = _get(f"/works/{wid}", {"select": "referenced_works"})
    refs = full.get("referenced_works") or []
    print(f"# {len(refs)} references of: {fmt(w)}")
    for chunk_start in range(0, min(len(refs), args.n), 50):
        chunk = refs[chunk_start:chunk_start + 50]
        ids = "|".join(r.rsplit("/", 1)[-1] for r in chunk)
        show(_get("/works", {"filter": f"openalex:{ids}", "per-page": 50, "select": SELECT}), args, header=False)


def cmd_author(args):
    a = _get("/authors", {"search": args.name, "per-page": 3, "select": "id,display_name,works_count,summary_stats,last_known_institutions"})
    if not a or not a.get("results"):
        sys.exit("no author match")
    cands = a["results"]
    for c in cands[1:3]:
        inst = (c.get("last_known_institutions") or [{}])
        inst = inst[0].get("display_name", "?") if inst else "?"
        print(f"# other candidate: {c['display_name']} ({inst}, {c['works_count']} works, {c['id']})", file=sys.stderr)
    au = cands[0]
    aid = au["id"].rsplit("/", 1)[-1]
    inst = (au.get("last_known_institutions") or [{}])
    inst = inst[0].get("display_name", "?") if inst else "?"
    print(f"# top author match: {au['display_name']} ({inst}, {au['works_count']} works)")
    f = [f"authorships.author.id:{aid}"] + common_filters(args)
    params = {"filter": ",".join(f), "per-page": args.n, "select": SELECT,
              "sort": "publication_date:desc" if args.recent else "cited_by_count:desc"}
    show(_get("/works", params), args)


def cmd_published(args):
    params = {"search": _clean(args.title), "filter": "type:article", "per-page": 5, "select": SELECT}
    data = _get("/works", params)
    hits = [(_title_sim(args.title, w.get("display_name") or ""), w)
            for w in data.get("results", []) if not is_wp(w)]
    hits = sorted([h for h in hits if h[0] >= 0.5], key=lambda x: -x[0])
    if not hits:
        print("NO published-article match found (title similarity >= 0.5).")
        print("The work may be unpublished, or published under a changed title — retry with distinctive title words.")
        return
    print("# candidate published versions (verify authors; confirm the year independently — see CAUTION in --help):")
    for i, (sim, w) in enumerate(hits[:3], 1):
        print(f"sim={sim:.2f}  {fmt(w, i)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(p, with_type=True):
        p.add_argument("-n", type=int, default=10, help="max results")
        if with_type:
            p.add_argument("--type", help="article | preprint | book-chapter | report ...")
        p.add_argument("--source", help="journal ISSN (e.g. 0304-405X) or name")
        p.add_argument("--from-year", type=int)
        p.add_argument("--to-year", type=int)
        p.add_argument("--json", action="store_true")

    p = sub.add_parser("search", help="relevance search (10 credits)")
    p.add_argument("query")
    p.add_argument("--cited", action="store_true", help="sort matches by citation count (find classics)")
    add_common(p)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("filter", help="filtered listing, no text ranking (1 credit)")
    p.add_argument("--title", help="title word search (title.search filter)")
    p.add_argument("--raw", help="raw OpenAlex filter string, comma-joined")
    p.add_argument("--cited", action="store_true")
    add_common(p)
    p.set_defaults(func=cmd_filter)

    p = sub.add_parser("doi", help="fetch by DOI(s)")
    p.add_argument("dois", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doi)

    p = sub.add_parser("cited-by", help="papers citing DOI, most-cited first")
    p.add_argument("doi")
    add_common(p)
    p.set_defaults(func=cmd_cited_by)

    p = sub.add_parser("refs", help="papers a DOI cites")
    p.add_argument("doi")
    add_common(p)
    p.set_defaults(func=cmd_refs)

    p = sub.add_parser("author", help="an author's works (most-cited first)")
    p.add_argument("name")
    p.add_argument("--recent", action="store_true", help="sort by date instead of citations")
    add_common(p)
    p.set_defaults(func=cmd_author)

    p = sub.add_parser("published", help="published version of a working-paper title (10 credits)")
    p.add_argument("title")
    p.set_defaults(func=cmd_published)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
