"""backlink-guard: check a link source before you submit to it, and watch your own links.

  python -m backlink_guard find "<keyword>" [more ...] [--site yoursite.com] [--skip site|file] [--vet] [--limit 30] [--fresh] [--json]
  python -m backlink_guard vet <site> [more ...] [--from list.xlsx|.csv|.md|.json] [--skip site|file] [--limit 30] [--topic "keyword"] [--referrals ga4.csv] [--deep] [--recent] [--free] [--fresh] [--json]
  python -m backlink_guard recheck [--to your-domain] [--deep] [--free] [--fresh] [--json]
  python -m backlink_guard audit <your-domain> [--deep] [--sitewide 20] [--rows 1000] [--homes 300] [--fresh] [--json]
  python -m backlink_guard lost <your-domain> [--sitewide 20] [--rows 1000] [--fresh] [--json]
  python -m backlink_guard competitors <your-domain> --vs <competitor> [more ...] [--days 7] [--limit 100] [--max-usd 0.30] [--fresh] [--json]
  python -m backlink_guard cited <your-domain> "<keyword>" [more ...] [--max-usd 0.10] [--fresh] [--json]
  python -m backlink_guard questions "<what you make>" [--count 10] [--plain] [--fresh] [--json]
  python -m backlink_guard asked <your-domain> ["<question>" ...] [--file questions.txt] [--name "Your Brand"]
                                 [--engines chatgpt,ai_mode,perplexity,claude,gemini] [--samples N] [--rank] [--max-usd 1.00] [--fresh] [--json]
  python -m backlink_guard verify <page-url> --to <your-domain> [--json]
  python -m backlink_guard log                                  the record, with pace and anchor checks
  python -m backlink_guard log add <site> --kind directory [--anchor TEXT] [--paid USD] [--url URL] [--note TEXT]
  python -m backlink_guard log set <site> --status live [--url URL]
  python -m backlink_guard mcp                                  the MCP server on stdio (needs the `mcp` package)

find    the pages that rank for your keywords (directories, lists, articles, videos,
        threads), sorted by the visitors they get from those searches, with what can be done
        on each: $0.005 a keyword plus $0.012 for the search volumes. --vet then vets the sites.
vet     reads each site, and with keys asks for its rating, a year of visits and its
        spam score: about $0.01 a site plus $0.025 for the batch. --free reads the site only.
        --from reads the sites out of a list file; --limit caps how many are checked.
        --topic adds where each site ranks for your keyword ($0.005 a keyword).
        --referrals reads your analytics export (GA4 Session source and Sessions) and shows
        what each site has sent you. A site its own pages put at avoid gets no paid check.
recheck the sites in your log checked again and compared with the last look: what got
        worse, and with --to, whether your links are still there. Monthly is enough.
audit   your own profile: totals, new and lost referring domains by week, anchors with their
        referring domains, site-wide links (one site linking from many of its pages, counted once),
        the spam score of the sites linking to you, and the referring domains one owner runs (three
        or more on one analytics or ads account, from their home pages, free; about $0.035 more
        when the backlinks name fewer sites than --homes): about $0.11, with --deep about $0.15.
lost    links to pages of yours that answer 404 or 410, by referring domains, each with the
        closest live page in your sitemaps to 301 it to, and the pages of yours that redirect,
        followed hop by hop: soft-lost (to your home page, another site or an unrelated page,
        with a closer page suggested), temporary, chained or broken. The same backlinks as audit
        (about $0.06, nothing more after an audit the same week); asking your pages is free.
competitors
        the sites your competitors earned links from and you lack: each one's referring domains
        first seen in the last --days days, and the sites linking to two or more of them but not
        to you, each with a linking page and what to do there. About $0.025 a call: 2 competitors
        about $0.15, 3 about $0.20; --max-usd caps it (default $0.30).
cited   which sites Google's AI Overview cites for your keywords, whether you are one of them,
        and the sites cited most across them: the places to be mentioned on. $0.002 a keyword
        (up to $0.004); a keyword with no AI Overview is said so.
questions
        how people would ask an AI assistant for what you make: ChatGPT, Claude and Gemini each
        write the questions they expect (about $0.01). --plain prints the list for a file.
asked   your questions to ChatGPT, Google's AI Mode, Perplexity, Claude and Gemini: what each one
        searched for, the pages it cited with their titles, the tools it named, whether it named
        you; then the sites and pages cited most (the places to be mentioned on) and the searches
        they ran. About $0.12 a question (ChatGPT and Perplexity asked twice); --max-usd caps it.
        --rank then looks up each of their searches on Google and Bing (top 20): where you rank,
        and which sites rank against which ones were cited. $0.0035 a search on each.
verify  whether a page links to you and whether that link passes ranking credit. Free.
log     kept in state/ledger.jsonl on this machine. Free.

Keys: GOANYAPI_API_KEY (rating, visits, index, your backlinks), and GLASSER_API_KEY or
AISA_API_KEY (spam scores, weekly new and lost domains, anchors, competitors' referring
domains, AI Overviews; through Glasser when both are set). questions, asked, --deep's Ahrefs
and Semrush numbers and the site: search that stands in for GoAnyAPI's need AISA_API_KEY.
Each is optional; what is missing is said.
"""
from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path

from . import find as finding
from . import asked as asking
from . import cited, competitors, ledger, links, lists, lost, owners, page, profile, recheck, report
from . import verify as verification
from . import vet as vetting

LIMIT = 30          # sites a run checks unless told otherwise: about $0.30 with both keys


def _print(args, data, text: str) -> int:
    print(json.dumps(data, ensure_ascii=False, indent=1, default=sorted) if args.json else text)
    return 0


def skipped(args) -> set[str]:
    return {page.site(x) for s in args.skip for x in (lists.read(s) if Path(s).is_file() else [s])}


def cmd_find(args) -> int:
    result = finding.find(args.keywords, own=args.site or "", skip=tuple(skipped(args)), fresh=args.fresh)
    vetted = {}
    if args.vet:
        sites = finding.to_vet(result, args.limit)
        checked = vetting.vet(sites, fresh=args.fresh, topics=tuple(args.keywords)) if sites else {"rows": [], "cost": 0, "errors": []}
        result["vet"], result["cost"] = checked, result["cost"] + checked["cost"]
        vetted = {r["domain"]: r["grade"] for r in checked["rows"]}
    text = report.find(result, vetted)
    if args.vet and result["vet"]["rows"]:
        text += "\n\n" + report.vet(result["vet"])
    return _print(args, result, text)


def targets_of(args) -> list[str]:
    """The sites given and the sites in --from, once each, at most --limit of them."""
    skip = skipped(args)
    found = [t for t in dict.fromkeys(args.targets + (lists.read(args.from_file) if args.from_file else []))
             if page.site(t) not in skip]
    if not found:
        raise SystemExit("vet: give sites, or a list with --from")
    if len(found) > args.limit:
        print(f"{len(found)} sites found; checking the first {args.limit} (raise --limit to check more)", file=sys.stderr)
    return found[:args.limit]


def cmd_log(args) -> int:
    if args.action == "add":
        if not args.site or not args.kind:
            raise SystemExit("log add: give the site and --kind")
        ledger.add(args.site, args.kind, args.anchor or "", args.paid or 0.0, args.url or "", args.note or "")
    elif args.action == "set":
        if not ledger.update(args.site or "", status=args.status, url=args.url, note=args.note):
            raise SystemExit(f"log set: no entry for {args.site}")
    rows = ledger.entries()
    flags = ledger.checks(rows)
    return _print(args, {"entries": rows, "flags": flags}, report.ledger(rows, flags))


def asked_parsers(sub, common) -> None:
    w = sub.add_parser("questions", parents=[common], description=(
        "How people would ask an AI assistant for what you make: ChatGPT, Claude and Gemini each write the questions they "
        "expect, without searching the web, then all of them once. AIsa: about $0.01 for the three."))
    w.add_argument("what", help="what you make, the way a buyer would put it")
    w.add_argument("--count", type=int, default=10, help="questions each assistant writes (default 10)")
    w.add_argument("--plain", action="store_true", help="print only the questions, one a line, for a file")
    w.add_argument("--max-usd", type=float, default=asking.WRITE_MAX_USD,
                   help=f"spend at most this much (default {asking.WRITE_MAX_USD:.2f})")
    q = sub.add_parser("asked", parents=[common], description=(
        "Your questions to ChatGPT (its own interface), Google's AI Mode, Perplexity, Claude and Gemini (with their web "
        "search): what each one searched for, the pages it cited with their titles, the tools it named, whether it named "
        "or cited you; then the sites and pages cited most and the searches they ran. AIsa: ChatGPT and AI Mode $0.004 "
        "an answer, Perplexity about $0.006, Claude and Gemini about $0.045; ChatGPT and Perplexity are asked twice."))
    q.add_argument("domain", help="your own domain")
    q.add_argument("questions", nargs="*", metavar="QUESTION")
    q.add_argument("--file", metavar="FILE", help="questions, one a line (# comments), from `questions --plain`")
    q.add_argument("--name", action="append", default=[], metavar="NAME", help="a name the answers may call you by; repeatable")
    q.add_argument("--engines", default=",".join(asking.ENGINES), help=f"comma-separated (default {','.join(asking.ENGINES)})")
    q.add_argument("--samples", type=int, help="ask every engine this many times (default: ChatGPT and Perplexity 2, others 1)")
    q.add_argument("--rank", action="store_true", help="look up each search they ran on Google and Bing (top 20, US): "
                   "$0.0035 a search on each, under the same cap; answers asked in the last 7 days come from the cache")
    q.add_argument("--max-usd", type=float, default=asking.MAX_USD,
                   help=f"spend at most this much on the run; cached answers are free (default {asking.MAX_USD:.2f})")


def cmd_asked(args) -> int:
    if args.command == "questions":
        result = asking.write_questions(args.what, count=args.count, max_usd=args.max_usd, fresh=args.fresh)
        if args.plain:
            print("\n".join(result["questions"]))
            return 0
        return _print(args, result, report.questions(result))
    found = list(args.questions) + (asking.from_file(args.file) if args.file else [])
    if not found:
        raise SystemExit("asked: give questions, or --file with one a line")
    result = asking.asked(args.domain, found, names=args.name, engines=args.engines.split(","), samples=args.samples,
                          max_usd=args.max_usd, fresh=args.fresh, rank=args.rank)
    return _print(args, result, report.asked(result))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m backlink_guard", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--fresh", action="store_true", help="ignore answers cached in the last 7 days")
    f = sub.add_parser("find", parents=[common])
    f.add_argument("keywords", nargs="+", metavar="KEYWORD")
    f.add_argument("--site", metavar="DOMAIN", help="your own site, left out of the results")
    f.add_argument("--skip", action="append", default=[], metavar="SITE_OR_FILE",
                   help="leave out these sites (competitors, ones you already have); repeatable, or a list file")
    f.add_argument("--vet", action="store_true", help="also vet the directories and article sites found (about $0.01 a site)")
    f.add_argument("--limit", type=int, default=LIMIT, help=f"vet at most this many sites (default {LIMIT})")
    v = sub.add_parser("vet", parents=[common])
    v.add_argument("targets", nargs="*")
    v.add_argument("--from", dest="from_file", metavar="FILE", help="a list to read sites from (.txt .md .csv .json .xlsx)")
    v.add_argument("--limit", type=int, default=LIMIT, help=f"check at most this many sites (default {LIMIT})")
    v.add_argument("--skip", action="append", default=[], metavar="SITE_OR_FILE",
                   help="leave out these sites (your own, competitors, ones you already have); repeatable, or a list file")
    v.add_argument("--free", action="store_true", help="read the sites only; call no paid API")
    v.add_argument("--deep", action="store_true",
                   help="also read each site's own backlink profile: badge networks, unproven sites (+$0.024 a site)")
    v.add_argument("--topic", action="append", default=[], metavar="KEYWORD",
                   help="your keyword: shows where each site ranks for it (+$0.005 a keyword); repeatable")
    v.add_argument("--recent", action="store_true",
                   help="also ask whether Google took in the site's pages from the last week and month (+$0.008 a site, slow)")
    v.add_argument("--referrals", metavar="FILE",
                   help="your analytics export of visitor sources (GA4 CSV: Session source, Sessions): shows what each site sent you")
    r = sub.add_parser("recheck", parents=[common])
    r.add_argument("--to", metavar="DOMAIN", default="", help="your domain: also check that your links are still there (free)")
    r.add_argument("--deep", action="store_true", help="also the backlink profile of each site (+$0.024 a site)")
    r.add_argument("--free", action="store_true", help="read the sites only; call no paid API")
    a = sub.add_parser("audit", parents=[common])
    a.add_argument("domain")
    a.add_argument("--deep", action="store_true", help="also the full anchor distribution")
    a.add_argument("--homes", type=int, default=owners.HOMES, metavar="SITES",
                   help=f"referring domains whose home pages are read for shared analytics or ads accounts, the most "
                        f"linking first (default {owners.HOMES}; 0 skips it). The pages are free; when the backlinks read "
                        f"name fewer sites, the list of referring domains (Glasser or AIsa) fills up (about $0.035 for 300)")
    o = sub.add_parser("lost", parents=[common])
    o.add_argument("domain")
    for x in (a, o):
        x.add_argument("--sitewide", type=int, default=links.SITEWIDE_PAGES, metavar="PAGES",
                       help=f"pages of one site linking to one page of yours that make a site-wide link (default {links.SITEWIDE_PAGES})")
        x.add_argument("--rows", type=int, default=links.ROWS, metavar="LINKS",
                       help=f"backlinks read one by one from Glasser or AIsa (default and most {links.ROWS}; about $0.06 for 1,000)")
    k = sub.add_parser("competitors", parents=[common], description=(
        "The sites your competitors earned links from and you lack: each one's referring domains first seen in the last "
        "--days days, and the sites linking to two or more of them but not to you, each with a linking page and what to "
        "do there. Sites on the shared spam-link list, links scoring 50 or more for spam and one network's template "
        "pages are left out and named. Glasser or AIsa: about $0.025 a call, 2N+2 calls for N competitors (three: about $0.20)."))
    k.add_argument("domain", help="your own domain: sites already linking to it are left out")
    k.add_argument("--vs", nargs="+", required=True, metavar="COMPETITOR", help="the competitors' domains")
    k.add_argument("--days", type=int, default=competitors.DAYS, help=f"new means first seen in this many days (default {competitors.DAYS})")
    k.add_argument("--limit", type=int, default=competitors.LIMIT,
                   help=f"referring domains read from each list (default {competitors.LIMIT}, most {competitors.ROWS_MAX})")
    k.add_argument("--max-usd", type=float, default=competitors.MAX_USD,
                   help=f"spend at most this much on the run; cached answers are free (default {competitors.MAX_USD:.2f})")
    t = sub.add_parser("cited", parents=[common], description=(
        "Which sites Google's AI Overview cites for each keyword (US, English), whether your domain is one of them and "
        "where you rank, then the sites cited most across the keywords: the places to be mentioned on. A keyword with no "
        "AI Overview is said so. AIsa: $0.002 a keyword, up to $0.004 when the overview loads late; Glasser: $0.004, "
        "up to $0.006."))
    t.add_argument("domain", help="your own domain")
    t.add_argument("keywords", nargs="+", metavar="KEYWORD")
    t.add_argument("--max-usd", type=float, default=cited.MAX_USD,
                   help=f"spend at most this much on the run; cached answers are free (default {cited.MAX_USD:.2f})")
    asked_parsers(sub, common)
    c = sub.add_parser("verify", parents=[common])
    c.add_argument("page")
    c.add_argument("--to", required=True, metavar="DOMAIN")
    g = sub.add_parser("log", parents=[common])
    g.add_argument("action", nargs="?", choices=["add", "set"])
    g.add_argument("site", nargs="?")
    g.add_argument("--kind", choices=ledger.KINDS)
    g.add_argument("--status", choices=ledger.STATUSES)
    for name in ("--anchor", "--url", "--note"):
        g.add_argument(name)
    g.add_argument("--paid", type=float)
    return p


def serve_mcp() -> int:
    """`backlink-guard mcp`: the stdio MCP server under the package's own name, so a client that only knows the
    PyPI name can start it (`uvx --with mcp backlink-guard mcp`)."""
    try:
        from . import mcp_server
    except ImportError:
        print('The MCP server needs the `mcp` package: pip install "backlink-guard[mcp]"', file=sys.stderr)
        return 1
    mcp_server.main()
    return 0


def main(argv: list[str] | None = None) -> int:
    if (sys.argv[1:] if argv is None else argv)[:1] == ["mcp"]:
        return serve_mcp()
    args = parser().parse_args(argv)
    if args.command == "vet":
        targets = targets_of(args)
        result = vetting.vet(targets, paid_sources=not args.free, fresh=args.fresh, recent=args.recent, deep=args.deep,
                             topics=tuple(args.topic), referrals=lists.referrals(args.referrals) if args.referrals else None)
        return _print(args, result, report.vet(result))
    if args.command == "recheck":
        result = recheck.run(own=args.to, paid_sources=not args.free, deep=args.deep, fresh=args.fresh)
        return _print(args, result, report.recheck(result))
    if args.command == "find":
        return cmd_find(args)
    if args.command == "audit":
        result = profile.audit(args.domain, deep=args.deep, fresh=args.fresh, sitewide=args.sitewide, rows=args.rows,
                               homes=args.homes)
        return _print(args, result, report.audit(result))
    if args.command == "lost":
        result = lost.lost(args.domain, fresh=args.fresh, rows=args.rows, sitewide=args.sitewide)
        return _print(args, result, report.lost(result))
    if args.command == "competitors":
        result = competitors.competitors(args.domain, args.vs, days=args.days, limit=args.limit, max_usd=args.max_usd,
                                         fresh=args.fresh)
        return _print(args, result, report.competitors(result))
    if args.command == "cited":
        result = cited.cited(args.domain, args.keywords, max_usd=args.max_usd, fresh=args.fresh)
        return _print(args, result, report.cited(result))
    if args.command in ("questions", "asked"):
        return cmd_asked(args)
    if args.command == "verify":
        result = verification.verify(args.page, args.to)
        return _print(args, result, report.verify(result))
    return cmd_log(args)


if __name__ == "__main__":
    sys.exit(main())
