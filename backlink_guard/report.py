"""Markdown for people; the same results are available as JSON with --json."""
from __future__ import annotations

from .policy import POLICY_URL

MARK = {"avoid": "⛔ avoid", "caution": "⚠️ caution", "ok": "✅ ok", "note": "ℹ️"}
MISSING = "–"


def usd(micros: int) -> str:
    return f"${micros / 1e6:.3f}"


def num(value) -> str:
    return MISSING if value is None or value == "" else f"{value:,}" if isinstance(value, (int, float)) else str(value)


def flag_lines(flags: list[dict]) -> list[str]:
    lines = []
    for f in flags:
        lines.append(f"  - {MARK.get(f['level'], f['level'])} **{f['meaning']}.** {f['evidence']}"
                     + (f" _(Google: {f['policy']})_" if f["policy"] else ""))
    return lines


def missing_sources(sources: dict) -> list[str]:
    if sources.get("free"):
        return ["- Run with `--free`: rating, visits, index status, spam scores and Google search history were not checked. "
                "A site can pass the page checks and still have no audience."]
    lines = []
    if not sources.get("goanyapi"):
        lines.append("- No `GOANYAPI_API_KEY`: rating, visits and index status were not checked. A site can pass the page checks and still have no audience.")
    if not sources.get("aisa"):
        lines.append("- No `AISA_API_KEY`: spam scores and Google search history were not checked.")
    return lines


def fit_text(m: dict) -> str:
    """Where a site stands on your topics: it ranks for one, it writes about one, or neither."""
    f = m.get("fit")
    if f:
        return f"#{f['position']} for \u201c{f['keyword']}\u201d"
    return "writes about it" if m.get("mentions") else MISSING


def vet(result: dict) -> str:
    topical = any("mentions" in r["metrics"] or "fit" in r["metrics"] for r in result["rows"])
    head = "| Site | Verdict | Reach | Rating | Visits a month | Spam score |" + (" Fit |" if topical else "") + " Why |"
    lines = ["# Link sources checked", "", head, "|---" * head.count(" |") + "|"]
    for r in result["rows"]:
        m, why = r["metrics"], "; ".join(f["meaning"] for f in r["flags"] if f["level"] != "note") or MISSING
        lines.append(f"| {r['domain']} | {MARK[r['grade']]} | {r.get('reach') or MISSING} | {num(m.get('dr'))} | "
                     f"{num(m.get('visits'))} | {num(m.get('spam_score'))} |" + (f" {fit_text(m)} |" if topical else "")
                     + f" {why} |")
    for r in result["rows"]:
        if r["flags"]:
            lines += ["", f"**{r['domain']}**"] + flag_lines(r["flags"])
    notes = missing_sources(result["sources"]) + [f"- Failed: {e}" for e in result["errors"]]
    if notes:
        lines += ["", "**Incomplete**", *notes]
    lines += ["", f"A verdict is a set of signals with their evidence, not Google's judgment. Policy: {POLICY_URL}",
              f"Cost of this run: {usd(result['cost'])}."]
    return "\n".join(lines)


def audit(a: dict) -> str:
    t = a["totals"]
    lines = [f"# Link profile of {a['domain']}", ""]
    if t:
        lines += [f"- Rating {num(t.get('dr'))}; {num(t.get('backlinks'))} backlinks from {num(t.get('refdomains'))} referring domains",
                  f"- Passing ranking credit: {num(t.get('followed_backlinks'))} links from {num(t.get('followed_refdomains'))} domains"]
    if a["weeks"]:
        recent = ", ".join(f"{w['week'][5:]}: +{w['new']}/−{w['lost']}" for w in a["weeks"][-6:])
        lines.append(f"- New and lost referring domains by week: {recent}")
    lines += ["", "## Findings"] + (flag_lines(a["flags"]) or ["  - Nothing that reads as manufactured."])
    if a["worst_referrers"]:
        lines += ["", "## Linking sites with a high spam score", "| Site | Spam score |", "|---|---|"]
        lines += [f"| {w['site']} | {w['spam_score']} |" for w in a["worst_referrers"][:10]]
    if a["anchors"]:
        lines += ["", "## Anchors", "| Anchor | Links |", "|---|---|"]
        lines += [f"| {(text or '(empty)')[:70]} | {n} |" for text, n in a["anchors"][:12]]
    if a["top"]:
        lines += ["", "## Top linking pages", "| Page | Rating | Anchor |", "|---|---|---|"]
        lines += [f"| {x['from'][:80]} | {num(x['dr'])} | {(x['anchor'] or '(empty)')[:50]} |" for x in a["top"][:12]]
    if a["errors"]:
        lines += ["", "**Incomplete**"] + [f"- Failed: {e}" for e in a["errors"]]
    lines += ["", f"Cost of this run: {usd(a['cost'])}."]
    return "\n".join(lines)


def verify(v: dict) -> str:
    lines = [f"**{v['verdict']}** — {v['page']} → {v['domain']}"]
    if v["note"]:
        lines.append(v["note"])
    for l in v["links"]:
        rel = " ".join(l["rel"]) or "none"
        lines.append(f"- {l['how']}, {l['placement']}, rel: {rel}, anchor \"{l['anchor'][:60]}\"" + (" (http, redirects to https)" if l["insecure"] else ""))
    return "\n".join(lines)


def ledger(rows: list[dict], flags: list[dict]) -> str:
    lines = ["| Date | Where | Kind | Anchor | Paid | Status |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['date']} | {r['target']} | {r['kind']} | {r.get('anchor') or MISSING} | "
              f"{('$%g' % r['paid']) if r.get('paid') else MISSING} | {r['status']} |" for r in rows]
    return "\n".join(lines + ([""] + flag_lines(flags) if flags else []))


def find(result: dict, vetted: dict | None = None) -> str:
    """The pages that get your searches, busiest first, with what can be done on each."""
    vetted = vetted or {}
    lines = ["# Pages that get the searches you want", "", "| Keyword | Searches a month (US) | Difficulty |", "|---|---|---|"]
    lines += [f"| {k} | {num(v.get('volume'))} | {num(v.get('kd'))} |" for k, v in result["keywords"].items()]
    sources = [p for p in result["pages"] if p["kind"] not in ("docs", "site")]
    others = [p for p in result["pages"] if p["kind"] in ("docs", "site")]
    head = "| Page | Kind | Ranks | Visitors from these searches |" + (" Verdict |" if vetted else "") + " What to do |"
    lines += ["", head, "|---" * head.count(" |") + "|"]
    for p in sources:
        ranks = "; ".join(f"#{x['position']} {x['keyword']}" for x in p["ranks"])
        verdict = vetted.get(p["domain"])
        lines.append(f"| [{p['title'] or p['domain']}]({p['url']}) | {p['kind']} | {ranks} | about {p['visitors']:,} |"
                     + (f" {MARK[verdict] if verdict else MISSING} |" if vetted else "") + f" {p['action']} |")
    if others:
        lines += ["", "Not link sources (official docs, products' own pages): "
                  + ", ".join(f"{p['domain']} (#{min(x['position'] for x in p['ranks'])})" for p in others[:12])]
    notes = [f"- Failed: {e}" for e in result["errors"]]
    if notes:
        lines += ["", "**Incomplete**", *notes]
    lines += ["", "Visitors = monthly searches times the share of clicks that position usually gets: a size, not a count. "
              "A page on a shared platform (GitHub, Medium, YouTube, Reddit) is judged by the page and its author, "
              "not by the platform's numbers. Never pay for a followed link: a paid mention carries rel=\"sponsored\" or nofollow.",
              f"Cost of this run: {usd(result['cost'])}."]
    return "\n".join(lines)
