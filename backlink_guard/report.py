"""Markdown for people; the same results are available as JSON with --json."""
from __future__ import annotations

from .policy import POLICY, POLICY_URL

MARK = {"avoid": "⛔ avoid", "caution": "⚠️ caution", "ok": "✅ ok", "incomplete": "❔ incomplete", "note": "ℹ️"}
MISSING = "–"
POLICY_MARK = {"avoid": "⛔", "caution": "⚠️"}
ACTION_MARK = {"skip": "⛔ skip", "look first": "🔍 look first", "free only": "🆓 free only", "low value": "💤 low value",
               "submit": "✅ submit"}


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


def sources_text(m: dict) -> str:
    """"search 62% · direct 25% · social 6%": where its visitors come from, biggest first."""
    parts = [(k, v) for k, v in (m.get("sources") or {}).items() if v >= 0.01][:3]
    return " · ".join(f"{k} {v * 100:.0f}%" for k, v in parts) or MISSING


def audience_lines(rows: list[dict]) -> list[str]:
    """Age, visitors and identity, plus the --deep numbers when they were asked for."""
    keys = ("registered", "sources", "entity")
    if not any(k in r["metrics"] for r in rows for k in keys):
        return []
    deep = any("ahrefs_dr" in r["metrics"] or "semrush_traffic" in r["metrics"] for r in rows)
    head = "| Site | First archived | Registered | Visitors from | From AI assistants | Google knows it as |"
    head += " Ahrefs DR | Semrush keywords / visits (US) | ChatGPT mentions | Built with |" if deep else ""
    out = ["", "## Audience and identity", "", head, "|---" * head.count(" |") + "|"]
    for r in rows:
        m = r["metrics"]
        ai = f"{m['ai_share'] * 100:.1f}%" if m.get("ai_share") is not None else MISSING
        line = (f"| {r['domain']} | {m.get('first_seen') or MISSING} | {m.get('registered') or MISSING} | {sources_text(m)} | "
                f"{ai} | {m.get('entity') or 'not an entity'} |")
        if deep:
            semrush = f"{num(m.get('semrush_keywords'))} / {num(m.get('semrush_traffic'))}"
            line += (f" {num(m.get('ahrefs_dr'))} | {semrush} | {num(m.get('ai_mentions'))} | "
                     f"{', '.join((m.get('tech') or [])[:4]) or MISSING} |")
        out.append(line)
    return out


def network_lines(networks: list[dict]) -> list[str]:
    """One operator's sites that the shared list lacks, each with its filled-in report."""
    if not networks:
        return []
    out = ["", "## Networks not on the shared list yet", "",
           "These sites came up as one operator's, most of them flagged here. A report adds them to the shared list of "
           "spam-link sources once a maintainer has checked the evidence; opening the link sends nothing."]
    for n in networks:
        how = f"titled \"{n['key'][:60]}\"" if n["kind"] == "template" else f"on one account ({n['key']})"
        more = f" and {len(n['unlisted']) - 6} more" if len(n["unlisted"]) > 6 else ""
        out.append(f"- {len(n['sites'])} sites {how}; not listed: {', '.join(n['unlisted'][:6])}{more}. [Report them]({n['report']})")
    return out


def vet(result: dict) -> str:
    topical = any("mentions" in r["metrics"] or "fit" in r["metrics"] for r in result["rows"])
    sent = any("sent_you" in r["metrics"] for r in result["rows"])
    head = ("| Site | Action | Verdict | Risk | Link policy | Value | Rating | Visits a month |" + (" Sent you |" if sent else "")
            + " Spam score |" + (" Fit |" if topical else "") + " Why |")
    lines = ["# Link sources checked", "", head, "|---" * head.count(" |") + "|"]
    for r in result["rows"]:
        m, found = r["metrics"], [f for f in r["flags"] if f["level"] != "note"]
        policy = "; ".join(POLICY[f["flag"]] for f in found if f["flag"] in POLICY)
        why = "; ".join([f["meaning"] for f in found if f["flag"] not in POLICY]
                        + ([f"not checked: {', '.join(r['missing'])}"] if r.get("missing") else [])) or MISSING
        policy = f"{POLICY_MARK.get(r.get('policy'), '')} {policy}".strip() or MISSING
        lines.append(f"| {r['domain']} | {ACTION_MARK.get(r.get('action'), MISSING)} | {MARK[r['grade']]} | {num(r.get('risk'))} | {policy} |"
                     + f" {r.get('value') or MISSING} | {num(m.get('dr'))} | {num(m.get('visits'))} |"
                     + (f" {num(m.get('sent_you'))} |" if sent else "") + f" {num(m.get('spam_score'))} |"
                     + (f" {fit_text(m)} |" if topical else "") + f" {why} |")
    lines += ["", "Action reads the rest together. Skip: avoid, nobody can reach it, or findings against it and almost no "
                  "visitors. Look first: a check failed or was refused, it may be one of an operator's several sites, or two "
                  "findings stand against it. Free only: it sells followed links or wants a link or badge back, so list "
                  "there for free and never pay or link back. Low value: nothing against it, but under 1,000 visits a month. "
                  "Submit: none of these.",
              "", "Verdict weighs everything: one avoid finding makes avoid, and it takes two caution findings to make caution. "
                  "Link policy lists what a link there would mean under Google's link spam policies, one finding being enough. "
                  "Value is what a listing can bring: the site's reach, or none when nobody can reach it (dead, parked, dropped "
                  "by Google, a shortener, a network page). Risk: 3 for each avoid finding, 1 for each caution. Incomplete: it "
                  "looked ok, but a check that could have found something failed; run it again."]
    lines += audience_lines(result["rows"])
    for r in result["rows"]:
        if r["flags"] or r.get("action_reason"):
            todo = f" — {ACTION_MARK[r['action']]}: {r['action_reason']}" if r.get("action_reason") else ""
            lines += ["", f"**{r['domain']}**{todo}"] + flag_lines(r["flags"])
    lines += network_lines(result.get("networks") or [])
    skipped = [r["domain"] for r in result["rows"] if r.get("skipped")]
    notes = missing_sources(result["sources"]) + [f"- Failed: {e}" for e in result["errors"]]
    if skipped:
        lines += ["", f"Paid checks skipped for {len(skipped)} site(s) its own pages already put at avoid: {', '.join(skipped[:12])}"
                  + (" …" if len(skipped) > 12 else "") + "."]
    if notes:
        lines += ["", "**Incomplete**", *notes]
    lines += ["", f"A verdict is a set of signals with their evidence, not Google's judgment. Policy: {POLICY_URL}",
              f"Cost of this run: {usd(result['cost'])}."]
    return "\n".join(lines)


def recheck(result: dict) -> str:
    """What changed on the sites you already have links on, then the check itself."""
    since = f" (last look {result['previous']})" if result["previous"] else " (first look: nothing to compare yet)"
    lines = [f"# The sites you have links on, {result['date']}{since}", ""]
    if not result["sites"]:
        return "\n".join(lines + ["No submitted or live entries in the log yet: `log add <site> --kind directory`."])
    lines += ["## Changed", *([f"- {c}" for c in result["changes"]] or ["- Nothing got worse."])]
    gone = [u for u, v in result["links"].items() if v != "followed link" and v != "qualified link"]
    if gone:
        lines += ["", "## Links not found as they were", *[f"- {u}: {result['links'][u]}" for u in gone]]
    return "\n".join(lines + ["", vet(result["vet"])])


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
