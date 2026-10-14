"""backlink-guard: check a link source before you submit to it, and watch your own links.

  python -m backlink_guard vet <site> [more ...] [--from list.xlsx|.csv|.md|.json] [--skip site|file] [--limit 30] [--free] [--fresh] [--json]
  python -m backlink_guard audit <your-domain> [--deep] [--fresh] [--json]
  python -m backlink_guard verify <page-url> --to <your-domain> [--json]
  python -m backlink_guard log                                  the record, with pace and anchor checks
  python -m backlink_guard log add <site> --kind directory [--anchor TEXT] [--paid USD] [--url URL] [--note TEXT]
  python -m backlink_guard log set <site> --status live [--url URL]

vet     reads each site, and with keys asks for its rating, a year of visits and its
        spam score: about $0.01 a site plus $0.025 for the batch. --free reads the site only.
        --from reads the sites out of a list file; --limit caps how many are checked.
audit   your own profile: totals, new and lost referring domains by week, anchors, and
        the spam score of the sites linking to you: about $0.06, with --deep about $0.10.
verify  whether a page links to you and whether that link passes ranking credit. Free.
log     kept in state/ledger.jsonl on this machine. Free.

Keys: GOANYAPI_API_KEY (rating, visits, index, your backlinks) and AISA_API_KEY (spam
scores, weekly new and lost domains, anchors). Each is optional; what is missing is said.
"""
from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path

from . import ledger, lists, page, profile, report
from . import verify as verification
from . import vet as vetting

LIMIT = 30          # sites a run checks unless told otherwise: about $0.30 with both keys


def _print(args, data, text: str) -> int:
    print(json.dumps(data, ensure_ascii=False, indent=1, default=sorted) if args.json else text)
    return 0


def targets_of(args) -> list[str]:
    """The sites given and the sites in --from, once each, at most --limit of them."""
    skip = {page.site(x) for s in args.skip for x in (lists.read(s) if Path(s).is_file() else [s])}
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


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m backlink_guard", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--fresh", action="store_true", help="ignore answers cached in the last 7 days")
    v = sub.add_parser("vet", parents=[common])
    v.add_argument("targets", nargs="*")
    v.add_argument("--from", dest="from_file", metavar="FILE", help="a list to read sites from (.txt .md .csv .json .xlsx)")
    v.add_argument("--limit", type=int, default=LIMIT, help=f"check at most this many sites (default {LIMIT})")
    v.add_argument("--skip", action="append", default=[], metavar="SITE_OR_FILE",
                   help="leave out these sites (your own, competitors, ones you already have); repeatable, or a list file")
    v.add_argument("--free", action="store_true", help="read the sites only; call no paid API")
    a = sub.add_parser("audit", parents=[common])
    a.add_argument("domain")
    a.add_argument("--deep", action="store_true", help="also the full anchor distribution")
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


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "vet":
        targets = targets_of(args)
        result = vetting.vet(targets, paid_sources=not args.free, fresh=args.fresh)
        return _print(args, result, report.vet(result))
    if args.command == "audit":
        result = profile.audit(args.domain, deep=args.deep, fresh=args.fresh)
        return _print(args, result, report.audit(result))
    if args.command == "verify":
        result = verification.verify(args.page, args.to)
        return _print(args, result, report.verify(result))
    return cmd_log(args)


if __name__ == "__main__":
    sys.exit(main())
