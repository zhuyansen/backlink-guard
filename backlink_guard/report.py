"""Markdown for people; the same results are available as JSON with --json."""
from __future__ import annotations

import urllib.parse
from collections import Counter

from .competitors import SHOWN
from .find import ACTIONS
from .links import clean
from .newcomers import NEWEST, YOUNG_DAYS as NEW_SITE_DAYS
from .policy import POLICY, POLICY_URL, REDIRECTS_URL, SITE_MOVE_URL

MARK = {"avoid": "⛔ avoid", "caution": "⚠️ caution", "ok": "✅ ok", "incomplete": "❔ incomplete", "note": "ℹ️"}
MISSING = "–"
POLICY_MARK = {"avoid": "⛔", "caution": "⚠️"}
ACTION_MARK = {"skip": "⛔ skip", "look first": "🔍 look first", "free only": "🆓 free only", "low value": "💤 low value",
               "submit": "✅ submit"}
VERDICT_MARK = {"broken": "⛔ broken", "soft_lost": "🔻 soft-lost", "temporary": "⚠️ temporary", "chain": "⚠️ chain",
                "fine": "✅ fine"}


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
    if not sources.get("glasser") and not sources.get("aisa"):
        lines.append("- No `GLASSER_API_KEY` or `AISA_API_KEY`: spam scores and Google search history were not checked.")
    elif sources.get("deep") and not sources.get("aisa"):
        lines.append("- No `AISA_API_KEY`: `--deep` left out Ahrefs' rating and Semrush's numbers (Glasser does not sell them).")
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
    deep = any(k in r["metrics"] for r in rows for k in ("ahrefs_dr", "semrush_traffic", "ai_mentions", "tech"))
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
    lines += newcomer_lines(result["rows"])
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


def takes_new_text(n: dict | None) -> str:
    """newcomers.takes_new in a few words."""
    if n is None:
        return "not read: the site does not answer"
    if n["unknown"]:
        return f"unknown: {n['unknown']}"
    seen = ", ".join(f"{e['site']} ({e['age_days']} days)" for e in n["examples"][:3])
    return (f"{n['young']} of {n['dated']} sites its newest pages link to were registered under {NEW_SITE_DAYS // 30} "
            f"months before" + (f": {seen}" if seen else "") + f" (newest page {n['newest']})")


def newcomer_lines(rows: list[dict]) -> list[str]:
    """Whether each source still takes new sites, when the run asked (vet --newcomers)."""
    asked = [r for r in rows if "newcomers" in r]
    if not asked:
        return []
    return (["", "## Does it still take new sites?", "",
             f"Read off its {NEWEST} newest sitemap pages: the sites they link to from their body, dated by registration "
             "(RDAP) or, when the registry keeps no RDAP record, by their first archived copy. None of them new: if those "
             "pages are its listings, it lists established sites, and a new site may not get in; open one to see. "
             "Informs, and does not change the verdict."]
            + [f"- **{r['domain']}**: {takes_new_text(r['newcomers'])}" for r in asked])


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
    lines += links_read_lines(a.get("links") or {})
    if a["weeks"]:
        recent = ", ".join(f"{w['week'][5:]}: +{w['new']}/−{w['lost']}" for w in a["weeks"][-6:])
        lines.append(f"- New and lost referring domains by week: {recent}")
    lines += ["", "## Findings"] + (flag_lines(a["flags"]) or ["  - Nothing that reads as manufactured."])
    if a["worst_referrers"]:
        lines += ["", "## Linking sites with a high spam score", "| Site | Spam score |", "|---|---|"]
        lines += [f"| {w['site']} | {w['spam_score']} |" for w in a["worst_referrers"][:10]]
    if a["anchors"]:
        once = " (a site-wide source counted once)" if (a.get("links") or {}).get("sitewide") else ""
        lines += ["", f"## Anchors{once}", "| Anchor | Links | Referring domains |", "|---|---|---|"]
        lines += [f"| {(x[0] or '(empty)')[:70]} | {x[1]:,} | {num(x[2]) if len(x) > 2 else MISSING} |" for x in a["anchors"][:12]]
    lines += sitewide_lines((a.get("links") or {}).get("sitewide") or [])
    lines += owner_lines(a.get("owners") or {})
    if a["top"]:
        lines += ["", "## Top linking pages", "| Page | Rating | Anchor |", "|---|---|---|"]
        lines += [f"| {x['from'][:80]} | {num(x['dr'])} | {(x['anchor'] or '(empty)')[:50]} |" for x in a["top"][:12]]
    if a["errors"]:
        lines += ["", "**Incomplete**"] + [f"- Failed: {e}" for e in a["errors"]]
    lines += ["", f"Cost of this run: {usd(a['cost'])}."]
    return "\n".join(lines)


def links_read_lines(l: dict) -> list[str]:
    """The backlinks read one by one: how many, from how many sites, and the site-wide ones counted once."""
    if not l:
        return []
    of = f" of {l['total']:,}" if l.get("total", 0) > l["read"] else ""
    line = f"- Read one by one: {l['read']:,}{of} links from {l['domains']:,} referring domains ({l['source']})"
    return [line + (f"; {l['counted_once']}" if l.get("counted_once") else "")]


def sitewide_lines(groups: list[dict]) -> list[str]:
    if not groups:
        return []
    out = ["", "## Site-wide links (each counted once)", "| Site | Your page | Links | Its pages | In footer, sidebar or navigation |",
           "|---|---|---|---|---|"]
    out += [f"| {g['site']} | {path_of(g['to'])} | {g['links']:,} | {g['pages']:,} | {round(g['template'] * 100)}% |" for g in groups[:12]]
    return out


def path_of(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


def page_of(url: str, domain: str) -> str:
    """The path, with the host in front when it is not `domain` itself (a subdomain, or plain http)."""
    host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    return ("" if host == domain and url.startswith("https://") else url.split("://", 1)[0] + "://" + host) + path_of(url)


def answer(d: dict) -> str:
    return f"HTTP {d['status']}" if d["status"] else d["error"] or "no answer"


def strongest(d: dict, label: str) -> str:
    return f"{d['strongest']} ({label} {d['rank']:,})" if d.get("rank") is not None and label else d["strongest"]


def suggestion(d: dict) -> tuple[str, str]:
    s = d.get("suggest") or {}
    if s.get("url"):
        return f"301 to {path_of(s['url'])}", f"{s['score']:.2f}"
    return "no good match" + (f" (best {s['score']:.2f})" if s.get("score") else ""), MISSING


def lost(r: dict) -> str:
    """Pages of yours that are gone, most referring domains first, each with where it could be sent."""
    of = f" of {r['total']:,}" if r["total"] > r["read"] else ""
    lines = [f"# Links to pages of {r['domain']} that are gone or redirect", "",
             f"{r['read']:,}{of} backlinks read ({r['source'] or 'no source'}), from {r['domains']:,} referring domains; "
             f"{r['pages']:,} pages of yours get links, {r['checked']:,} asked for."]
    if r["dead"]:
        lines += ["", "| Page of yours | Answer | Referring domains | Links | Strongest referring domain | Suggestion | Match |",
                  "|---|---|---|---|---|---|---|"]
        for d in r["dead"]:
            via = f" (redirects to {page_of(d['final'], r['domain'])})" if clean(d["final"]) != clean(d["url"]) else ""
            to, score = suggestion(d)
            lines.append(f"| {page_of(d['url'], r['domain'])}{via} | {d['status']} | {d['domains']:,} | {d['links']:,} | "
                         f"{strongest(d, r['strength'])} | {to} | {score} |")
        read = f"{r['sitemap']:,} pages listed" if r["sitemap"] else "none found, so nothing to suggest"
        lines += ["", f"A suggestion is the page in your own sitemaps ({read}) whose path is closest to the dead one, "
                      "checked to be live; under a match of 0.50 none is given. Nothing has been redirected: "
                      "read each before you add a 301."]
    else:
        lines += ["", "No page of yours that gets links answers 404 or 410."]
    lines += ["", "## Findings"] + (flag_lines(r["flags"]) or ["  - Nothing lost."])
    for state, what in (("blocked", "Answered with an error other than 404 or 410 (not counted as dead)"), ("unreachable", "No answer (not counted as dead)")):
        if r[state]:
            lines += ["", f"**{what}**"] + [f"- {page_of(d['url'], r['domain'])}: {answer(d)}" for d in r[state][:12]]
    lines += redirect_lines(r)
    if r["errors"]:
        lines += ["", "**Incomplete**"] + [f"- Failed: {e}" for e in r["errors"]]
    lines += ["", f"Google on redirects: {REDIRECTS_URL}", f"Google on moving pages: {SITE_MOVE_URL}",
              f"Cost of this run: {usd(r['cost'])}."]
    return "\n".join(lines)


def hops_text(d: dict, domain: str) -> str:
    """"308 → /zh/go-global/weekly": each hop's status, then where the chain ends."""
    return " → ".join([str(h["status"]) for h in d.get("hops") or []] + [page_of(d["final"], domain)])


def redirect_lines(r: dict) -> list[str]:
    """The pages of yours that redirect where links lose something, worst first; the ones that redirect well in a line."""
    worse = [d for d in r["redirected"] if d["verdict"] != "fine"]
    well = [d for d in r["redirected"] if d["verdict"] == "fine"]
    lines = []
    if worse:
        lines += ["", "## Pages of yours that redirect", "",
                  "| Page of yours | Redirect | Referring domains | Links | Verdict | Suggestion | Match |", "|---|---|---|---|---|---|---|"]
        for d in worse:
            to, score = suggestion(d) if d["verdict"] == "soft_lost" else (MISSING, MISSING)
            lines.append(f"| {page_of(d['url'], r['domain'])} | {hops_text(d, r['domain'])} | {d['domains']:,} | {d['links']:,} | "
                         f"{VERDICT_MARK[d['verdict']]}: {cell('; '.join(d['why']))} | {to} | {score} |")
        lines += ["", "A permanent redirect (301, 308) tells Google the page has moved; a temporary one (302, 303, 307) "
                      "keeps the old URL in its results. Google follows up to ten hops but advises one, and says redirecting "
                      "many old URLs to one irrelevant page, such as the home page, \"might be treated as a soft 404 error\". "
                      "A soft-lost page's suggestion is found as for a dead one; a path is not content, so read it first."]
    if well:
        lines += ["", f"Redirected well (one permanent hop to a page like it): {len(well)} page(s), e.g. "
                  + ", ".join(f"{page_of(d['url'], r['domain'])} → {page_of(d['final'], r['domain'])}" for d in well[:4]) + "."]
    return lines


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


def cell(text) -> str:
    """Text that stays inside one Markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def linked(label: str, url: str) -> str:
    return f"[{cell(label)}]({url.replace(' ', '%20').replace('(', '%28').replace(')', '%29')})"


def example_cell(r: dict) -> str:
    """A row's linking page as a link: its title, or its path when it has none."""
    e = r.get("example")
    return linked((e["title"] or path_of(e["url"]))[:60], e["url"]) if e else MISSING


def kinds_lines(rows: list[dict]) -> list[str]:
    """What to do on each kind of page shown, once each."""
    kinds = list(dict.fromkeys(r["kind"] for r in rows if r.get("kind")))
    return ["", "What to do, by kind of page:"] + [f"- {k}: {ACTIONS[k]}" for k in kinds] if kinds else []


def rival_lines(rival: str, got: dict) -> list[str]:
    """One competitor's new referring domains, strongest first."""
    n, yours = got["total"], got["linking_you"]
    known = f"; {len(yours)} already link to you, left out" if yours else ""
    lines = ["", f"### {rival}: {n:,} new referring domain{'s' if n != 1 else ''}{known}", ""]
    if not got["rows"]:
        return lines + ["None that you lack."]
    lines += ["| Site | Rank | First seen | Linking page | Kind |", "|---|---|---|---|---|"]
    lines += [f"| {r['site']} | {num(r['rank'])} | {r['first_seen'] or MISSING} | {example_cell(r)} | {r['kind'] or MISSING} |"
              for r in got["rows"][:SHOWN]]
    return lines + (["", f"And {len(got['rows']) - SHOWN} more (--json)."] if len(got["rows"]) > SHOWN else [])


def shared_lines(r: dict) -> list[str]:
    """The sites that link to two or more of the competitors and not to you."""
    lines = ["", "## Sites linking to two or more of them, not to you", ""]
    if len(r["rivals"]) < 2:
        return lines + ["The link intersect needs two competitors or more."]
    if r["shared"] is None:
        return lines + ["Not read: see below."]
    rows = r["shared"]["rows"]
    lines += [f"{r['shared']['total']:,} in all, the strongest {len(rows):,} read.", ""] if rows else ["None."]
    if rows:
        lines += ["| Site | Links to | Rank | First seen | Linking page | Kind |", "|---|---|---|---|---|---|"]
        lines += [f"| {x['site']} | {', '.join(x['rivals'])} | {num(x['rank'])} | {x['first_seen'] or MISSING} | "
                  f"{example_cell(x)} | {x['kind'] or MISSING} |" for x in rows[:SHOWN]]
    return lines + (["", f"And {len(rows) - SHOWN} more (--json)."] if len(rows) > SHOWN else [])


def capped_lines(r: dict) -> list[str]:
    """What the cost cap left out, and what failed."""
    lines = []
    if r["left_out"]:
        lines += ["", f"**Not asked, over the cap of ${r['max_usd']:.2f}:** " + "; ".join(r["left_out"])
                  + ". Raise --max-usd to complete them."]
    if r["errors"]:
        lines += ["", "**Incomplete**"] + [f"- Failed: {e}" for e in r["errors"]]
    return lines


def competitors(r: dict) -> str:
    """Each competitor's new referring domains, then the link intersect, with a linking page for each site."""
    lines = [f"# Links your competitors earned: {r['domain']} against {', '.join(r['rivals'])}", "",
             f"## New in the last {r['days']} days (first seen since {r['since']})"]
    for rival, got in r["new"].items():
        lines += rival_lines(rival, got)
    lines += shared_lines(r)
    rows = [x for got in r["new"].values() for x in got["rows"][:SHOWN]] + ((r["shared"] or {}).get("rows") or [])[:SHOWN]
    lines += kinds_lines(rows)
    lines += ["", "Rank is what the site's links pass to the competitor, on the backlink index's 0 to 1,000 scale (the highest when it "
                  "links to several). First seen is when the index's crawler first found a link from the site to that "
                  "competitor: new to its index, which can be later than the link itself.",
              "", "These sites already cover your field. Submit where it fits, ask to be added to a list, offer an author "
                  "what the page lacks; vet a site before you spend time on it (`backlink-guard vet <site>`), since a site "
                  "that links to everyone in a field can be a directory that sells its listings or a network. Never pay "
                  "for a followed link."]
    lines += left_lines(r)
    lines += capped_lines(r)
    return "\n".join(lines + ["", f"Cost of this run: {usd(r['cost'])} (cap ${r['max_usd']:.2f})."])


def age_cell(c: dict | None) -> str:
    return MISSING if not c else ("" if c["exact"] else "≥") + f"{c['n']:,}"


def launch_text(w: dict) -> str:
    how = {"archive": "first archived copy", "first link": "first referring domain"}.get(w["from"], "")
    return f"{w['day']} ({how})" if w["day"] else MISSING


def age_lines(r: dict) -> list[str]:
    """Each site's referring domains at the same ages after launch, yours first."""
    lines = ["", "## The same age: referring domains 30, 60 and 90 days after launch", "",
             "| Site | Launched | 30 days | 60 days | 90 days | Now, all |", "|---|---|---|---|---|---|"]
    for site, b in r["sites"].items():
        name = f"**{site}** (you)" if site == r["domain"] else site
        c = b["counts"]
        lines.append(f"| {name} | {launch_text(b['launch'])} | {age_cell(c.get(30))} | {age_cell(c.get(60))} | "
                     f"{age_cell(c.get(90))} | {b['total']:,} |")
    lines += ["", "Lost ones count: what it had then. ≥: the list read stops before that day, so it had at least this many."]
    for site, b in r["sites"].items():
        w = b["launch"]
        if w["before_index"]:
            lines.append(f"- {site} is older than the backlink index (it begins 2019-01-15): its earliest links there are "
                         "the index's first crawl, not what it got at launch. Compare against younger competitors.")
        elif w["dormant"]:
            lines.append(f"- {site}: first archived {w['archived']}, first referring domain {w['first_link']}: the domain sat "
                         "unused first, so it is counted from its first referring domain.")
        for x in b["bursts"]:
            lines.append(f"- {site}, week {x['week']} (from {x['from']}): {x['n']} new referring domains, several times its "
                         f"usual week: {some(x['sites'])}. Launch week, as a rule: the sites in it are the channels it used.")
    return lines


def young_cell(row: dict) -> str:
    y = row.get("young")
    return f"{'✅ ' if y['recent'] else ''}{y['rival']} at {y['age_days']} days ({y['on']})" if y else MISSING


def vet_cell(row: dict) -> str:
    v = row.get("vet")
    if not v:
        return MISSING
    takes = v.get("takes_new")
    new = "" if not takes or takes["unknown"] or takes["dated"] == 0 else f"; {takes['young']}/{takes['dated']} new"
    return f"{ACTION_MARK.get(v.get('action'), MISSING)}{new}"


def checklist_lines(r: dict) -> list[str]:
    rows = r["checklist"]
    head = ("## Launch checklist: in the first 90 days of two or more of them, not linking to you" if len(r["rivals"]) > 1
            else f"## {r['rivals'][0] if r['rivals'] else ''}'s launch channels, not linking to you")
    lines = ["", head, ""]
    if not rows:
        return lines + ["None."]
    lines += ["| Site | Of | First seen | Rank | Linking page | Kind | Took a new site | Free vet |",
              "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {x['site']} | {', '.join(x['rivals'])} | {x['first_seen'] or MISSING} | {num(x['rank'])} | {example_cell(x)} | "
              f"{x['kind'] or MISSING} | {young_cell(x)} | {vet_cell(x)} |" for x in rows[:SHOWN]]
    lines += ["", f"And {len(rows) - SHOWN} more (--json)."] if len(rows) > SHOWN else []
    return lines + ["", "Took a new site: it linked to one of them under 90 days old, at that age; ✅ in the last half "
                        "year, so it still takes new sites. Free vet: what its own pages say (`vet --free`), and how many "
                        "of the sites its newest pages link to are new; run a full `vet` before you spend time on one."]


def early_rival_lines(site: str, b: dict, table: bool = True) -> list[str]:
    rest, n = b["rest"], len(b["rows"])
    first = b["counts"].get(90)
    lines = ["", f"### {site}: launched {launch_text(b['launch'])}; {age_cell(first)} referring domains in its first 90 days", ""]
    shown = "below" if table else "above"
    parts = [f"{n} live, followed and not site-wide are {shown}" if n else "none live, followed and not site-wide",
             f"{rest.get('lost', 0)} lost since", f"{rest.get('nofollow', 0)} nofollow only"]
    if rest.get("sitewide"):
        parts.append(f"site-wide, mostly its owner's other sites or partners and not channels: {some(rest['sitewide'])}")
    if b.get("yours"):
        parts.append(f"already linking to you: {some(b['yours'])}")
    lines.append("; ".join(parts) + ".")
    if b["rows"] and table:
        lines += ["", "| Site | First seen | Rank | Linking page | Kind | Took a new site |", "|---|---|---|---|---|---|"]
        lines += [f"| {x['site']} | {x['first_seen']} | {num(x['rank'])} | {example_cell(x)} | {x['kind'] or MISSING} | "
                  f"{young_cell(x)} |" for x in b["rows"][:SHOWN]]
        lines += ["", f"And {len(b['rows']) - SHOWN} more (--json)."] if len(b["rows"]) > SHOWN else []
    return lines


def early(r: dict) -> str:
    """The same-age comparison, the launch checklist, then each competitor's first 90 days."""
    lines = [f"# Your competitors' earliest links: {r['domain']} against {', '.join(r['rivals'])}", "",
             "What each one got in its first 90 days, oldest first: the channels it used at launch, which take a new site, "
             "unlike the strong sites that link to it today."]
    lines += age_lines(r)
    lines += checklist_lines(r)
    lines += ["", "## Each competitor's first 90 days"]
    for site, b in r["sites"].items():
        if site != r["domain"]:
            lines += early_rival_lines(site, b, table=len(r["rivals"]) > 1)    # one: its table is the checklist
    rows = r["checklist"][:SHOWN] + [x for s, b in r["sites"].items() if s != r["domain"] for x in b["rows"][:SHOWN]]
    lines += kinds_lines(rows)
    lines += ["", "First seen is when the backlink index's crawler first found the site's link: it can be later than the "
                  "link itself. Launched is the Wayback Machine's first copy, or the first referring domain when that is "
                  "earlier. Never pay for a followed link."]
    lines += left_lines(r)
    lines += capped_lines(r)
    return "\n".join(lines + ["", f"Cost of this run: {usd(r['cost'])} (cap ${r['max_usd']:.2f})."])


def some(names: list[str], shown: int = 6) -> str:
    return ", ".join(names[:shown]) + (f" and {len(names) - shown} more" if len(names) > shown else "")


def left_lines(r: dict) -> list[str]:
    """The sites left out of the tables, and why: listed, links that score high for spam, one network's template."""
    listed = [d["site"] for d in r["dropped"] if d["why"] == "listed"]
    spammy = [f"{d['site']} ({d['why'].split()[-1]})" for d in r["dropped"] if d["why"] != "listed"]
    lines = ["", "**Left out**"] if listed or spammy or r["networks"] else []
    if listed:
        lines.append(f"- On the shared spam-link list: {len(listed)}: {some(listed)}.")
    if spammy:
        lines.append(f"- Links to the competitor scoring 50 or more for spam: {len(spammy)}: {some(spammy)}.")
    for n in r["networks"]:
        report_link = f" [Report them]({n['report']})" if n.get("report") else ""
        lines.append(f"- {len(n['sites'])} sites whose linking pages share one title, \"{cell(n['key'][:70])}\": one "
                     f"network's template: {some(n['sites'])}.{report_link}")
    return lines


def you_text(r: dict, domain: str) -> str:
    """Whether the overview cites you, and which page."""
    if not r["overview"]:
        return MISSING
    if not r["you"]:
        return "not cited"
    more = f" and {len(r['you']) - 1} more" if len(r["you"]) > 1 else ""
    return f"✅ cited: {page_of(r['you'][0], domain)}{more}"


def cited(c: dict) -> str:
    """Per keyword: whether there is an AI Overview, how many sites it cites, whether you are one; then the sites
    cited most across the keywords, the places to be mentioned on."""
    lines = [f"# Who Google's AI Overviews cite for your keywords ({c['domain']})", "",
             "| Keyword | AI Overview | Sites cited | You | Your position (organic) |", "|---|---|---|---|---|"]
    for r in c["keywords"]:
        sites = len({x["site"] for x in r["cited"]})
        lines.append(f"| {cell(r['keyword'])} | {'yes' if r['overview'] else 'no AI Overview'} | "
                     f"{sites if r['overview'] else MISSING} | {you_text(r, c['domain'])} | "
                     f"{'#' + str(r['rank']) if r['rank'] else 'not in the top 10'} |")
    if c["sites"]:
        lines += ["", "## The sites cited most", "", "| Site | Keywords | Citations | Page cited | Kind |", "|---|---|---|---|---|"]
        lines += [f"| {s['site']}{' (you)' if s['you'] else ''} | {len(s['keywords'])} | {s['citations']} | "
                  f"{linked((s['title'] or path_of(s['urls'][0]))[:60], s['urls'][0])} | {s['kind']} |" for s in c["sites"][:SHOWN]]
        lines += kinds_lines([s for s in c["sites"][:SHOWN] if not s["you"]])
    lines += ["", "An AI Overview cites the pages it was written from: a mention on the sites it cites most is how a site "
                  "gets into the answer, and a page of yours that ranks is often, not always, among them. \"No AI Overview\" "
                  "means Google showed none for this search today (US, English); another day or searcher can differ."]
    lines += capped_lines(c)
    return "\n".join(lines + ["", f"Cost of this run: {usd(c['cost'])} (cap ${c['max_usd']:.2f})."])


def questions(q: dict) -> str:
    """Step one: the questions each assistant expects to be asked, then all of them once."""
    lines = [f"# How people would ask an AI assistant for: {q['what']}"]
    for writer, found in q["by"].items():
        lines += ["", f"## {writer}", ""] + [f"- {x}" for x in found]
    lines += ["", f"## All of them once ({len(q['questions'])})", ""] + q["questions"]
    lines += ["", "Keep the ones your buyers would ask, one a line in a file, for `asked --file`. --plain prints only "
                  "the list."]
    lines += capped_lines(q)
    return "\n".join(lines + ["", f"Cost of this run: {usd(q['cost'])} (cap ${q['max_usd']:.2f})."])


def asked(a: dict) -> str:
    """How often each assistant named or cited you, the sites and pages they cite most, the searches they ran."""
    lines = [f"# What AI assistants answer when asked for what you make ({a['domain']})", "",
             f"{len(a['questions'])} questions, {len(a['answers'])} answers.", "",
             "| Assistant | Answers | Wrote your domain | Your name only | Cited you | Same-name site | Searches an answer "
             "| Pages cited an answer |", "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {e['engine']} | {e['answers']} | {e['named_you']} | {e['name_only']} | {e['cited_you']} | {e['lookalike']} | "
              f"{e['searches'] if e['engine'] != 'ai_mode' else MISSING} | {e['cited']} |" for e in a["by_engine"]]
    lines += ["", "\"Your name only\": the answer gave your name but not your domain, and no other site of that name was in "
                  "it. \"Same-name site\": the answer named or cited a site under your name with another ending; its "
                  "mentions are not counted as yours."]
    lines += asked_site_lines(a) + asked_page_lines(a["pages"]) + asked_search_lines(a["searches"])
    lines += asked_rank_lines(a.get("ranks"), a["domain"], a["max_usd"])
    if a["named"]:
        lines += ["", "## The tools they named", "",
                  "; ".join(f"{cell(n['name'])}{' (you)' if n['you'] else ''} ×{n['times']}" for n in a["named"][:20])]
    lines += ["", "An answer differs from one ask to the next: count what recurs. These answers come through APIs (US, "
                  "English, no history), not from a signed-in person's chat. Gemini cites through Google's redirect, so "
                  "only its sites are known, not its pages."]
    lines += capped_lines(a)
    return "\n".join(lines + ["", f"Cost of this run: {usd(a['cost'])} (cap ${a['max_usd']:.2f})."])


def asked_site_lines(a: dict) -> list[str]:
    if not a["sites"]:
        return []
    lines = ["", "## The sites cited most", "", "| Site | Answers | Assistants | Questions | A page cited | Kind |",
             "|---|---|---|---|---|---|"]
    shown = a["sites"][:SHOWN] + [s for s in a["sites"][SHOWN:] if s["you"] or s["lookalike"]]   # yours always shown
    lines += [f"| {s['site']}{' (you)' if s['you'] else ' (same name as you)' if s['lookalike'] else ''} | {s['answers']} | "
              f"{', '.join(s['engines'])} | {len(s['questions'])} | "
              f"{linked((s['title'] or path_of(s['urls'][0]))[:60], s['urls'][0])} | {s['kind']} |" for s in shown]
    return lines + kinds_lines([s for s in a["sites"][:SHOWN] if not s["you"]])


def asked_page_lines(pages: list[dict]) -> list[str]:
    shown = [p for p in pages if p["answers"] >= 2][:SHOWN]
    if not shown:
        return []
    return ["", "## Pages cited in two answers or more", "", "| Page | Answers | Assistants |", "|---|---|---|"] + [
        f"| {linked((p['title'] or path_of(p['url']))[:70], p['url'])} | {p['answers']} | {', '.join(p['engines'])} |"
        for p in shown]


def asked_search_lines(searches: list[dict]) -> list[str]:
    if not searches:
        return []
    return ["", "## What they searched for", "", "The searches the assistants ran before answering: what a page of yours "
            "could answer and be titled for (Google's AI Mode shows none).", ""] + [
        f"- {cell(s['query'])} (×{s['times']}: {', '.join(s['engines'])})" for s in searches[:20]]


def asked_rank_lines(r: dict | None, domain: str, max_usd: float) -> list[str]:
    """Where you rank on Google and Bing for the searches they ran, and the sites that rank for them against the
    answers that cited them."""
    if r is None:
        return []
    lines = ["", "## Where you rank for the searches they ran", ""]
    if not r["searches"]:
        return lines + ["No searches to look up: the assistants asked ran none that they show (AI Mode shows none)."]
    lines += [f"Each search above on Google and Bing (US, English, top {r['depth']}), the most-run first. An assistant "
              "reads what its search returns: a site missing from these results is rarely read at all, and one that "
              "ranks without being cited was passed over when the answer was written.", "",
              f"| Search engine | Searches read | You on the first page | You in the top {r['depth']} | Same-name site "
              "| Failed twice | Over the cap |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {e['engine']} | {e['searches']} | {e['you_first_page']} | {e['you']} | {e['lookalike']} | {e['failed']} | "
              f"{e['left_out']} |" for e in r["by_engine"]]
    lines += ranked_you_lines(r, domain) + ranked_site_lines(r["sites"])
    if r["cited_elsewhere"] and not r["left_out"]:
        lines += ["", "Cited without being on the first page of any search read, so read from another search or known to "
                      "the model already: " + "; ".join(f"{s['site']} ({s['answers']})" for s in r["cited_elsewhere"][:8])
                  + "."]
    failed = Counter(x[e]["error"] for x in r["searches"] for e in ("google", "bing") if "error" in x[e])
    if failed:
        lines += ["", "**Failed twice, not read as missing:** " + "; ".join(f"“{m}” ×{n}" for m, n in failed.items())]
    if r["left_out"]:
        lines += ["", f"**Not looked up, over the cap of ${max_usd:.2f}:** {len(r['left_out'])} lookups. Raise --max-usd "
                      "to complete them; the answers asked in the last 7 days are free."]
    return lines + ["", f"Lookups cost {usd(r['cost'])}."]


def ranked_you_lines(r: dict, domain: str) -> list[str]:
    def where(got: dict) -> str:
        if "first_page" not in got:
            return "failed" if "error" in got else "not looked up"
        return f"#{got['you']} ({page_of(got['your_page'], domain)})" if got["you"] else MISSING
    mine = [x for x in r["searches"] if any(x[e].get("you") for e in ("google", "bing"))]
    read = sum(any("first_page" in x[e] for e in ("google", "bing")) for x in r["searches"])
    if not mine:
        return ["", f"{domain} is in neither engine's top {r['depth']} for any of the {read} searches read."]
    return ["", f"Where {domain} ranks:", ""] + [
        f"- {cell(x['query'])} (×{x['times']}: {', '.join(x['assistants'])}): Google {where(x['google'])}, "
        f"Bing {where(x['bing'])}" for x in mine]


def ranked_site_lines(sites: list[dict]) -> list[str]:
    shown = sites[:SHOWN] + [s for s in sites[SHOWN:] if s["you"] or s["lookalike"]]
    if not shown:
        return []
    lines = ["", "### The sites on the first page of their searches", "",
             "| Site | Google: searches | Bing: searches | Answers citing it |", "|---|---|---|---|"]
    return lines + [f"| {s['site']}{' (you)' if s['you'] else ' (same name as you)' if s['lookalike'] else ''} | "
                    f"{s['google']} | {s['bing']} | {s['cited']} |" for s in shown]


def owner_lines(o: dict) -> list[str]:
    """The referring domains one owner runs, by the analytics or ads account their home pages report to."""
    if not o:
        return []
    lines = ["", "## One owner's sites among your referring domains", "",
             f"Home pages of {o['read']:,} referring domains read; {o['with_accounts']:,} report to an analytics or ads account."]
    if not o["groups"]:
        return lines + ["", "No account is shared by three sites or more with two of them linking to you."]
    lines += ["", "| Account | Sites linking to you | Links | Also in earlier checks | On the shared list |", "|---|---|---|---|---|"]
    lines += [f"| {g['key']} | {some(g['sites'])} | {g['links']:,} | {some(g['earlier']) or MISSING} | "
              f"{some(g['listed']) or MISSING} |" for g in o["groups"][:12]]
    lines += ["", "A network's links are one owner's votes: count it as one source. A network built to link to others is "
                  "the pattern Google's spam policies describe, but a media group's titles or a platform's hosted sites can "
                  "share an account honestly: read the sites before you act. Google ignores most such links; a disavow file "
                  "is for a manual action."]
    return lines + network_lines(o.get("networks") or [])
