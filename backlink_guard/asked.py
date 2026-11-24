"""What AI assistants answer when people ask them for what you make (0.8): the pages they read and cite, what they
search for, and whether they name you.

The three steps of working on AI answers, as two commands:
  questions  how would someone ask an assistant for this? ChatGPT, Claude and Gemini each write the questions they
             expect (no web search). About $0.01 for the three.
  asked      each question to ChatGPT (its own interface, through AIsa's LLM scraper), Google's AI Mode, Perplexity
             (sonar), Claude and Gemini (both with their web search): what each one searched for (its fan-out
             queries; AI Mode shows none), the pages it read and cited with their titles, the tools it named, and
             whether it named or cited you. Gemini's own app (gemini_app, the same LLM scraper as ChatGPT's, $0.004
             an answer) is asked only when named in --engines: its sources are what it cited, and it shows no
             searches. Then the tally across the answers: the sites and pages cited most (the
             places to be mentioned on, each with what can honestly be done there), the searches the assistants ran
             (what a page of yours could answer and be titled for), and how often each one named you.

An answer differs from one ask to the next, so the cheap engines are asked twice (SAMPLES). An answer through an API is
not the one a signed-in person sees: no history, no memory, US English. Prices on 2026-10-21 (AIsa): ChatGPT and AI
Mode $0.004 an answer, Perplexity about $0.006, Claude (Sonnet) and Gemini (Flash) about $0.045 with their web search:
about $0.12 a question with the default samples.

With rank, each search the assistants ran is then looked up on Google and Bing (US, English, top 20): an assistant
reads what its search returns, so a site missing from these results is rarely read at all, and one that ranks without
being cited was passed over when the answer was written. $0.0035 a search on each on 2026-10-26, under the same cap;
the answers themselves come from the cache when they were asked in the last 7 days.
"""
from __future__ import annotations

import re
import urllib.parse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import aisa, cited, find, page
from .budget import Budget, OverBudget

US, EN = 2840, "en"
ENGINES = {
    "chatgpt": {"path": "ai_optimization/chat_gpt/llm_scraper/live/advanced", "kind": "scraper", "estimate": 4_000},
    "gemini_app": {"path": "ai_optimization/gemini/llm_scraper/live/advanced", "kind": "scraper", "estimate": 4_000},
    "ai_mode": {"path": "serp/google/ai_mode/live/advanced", "kind": "serp", "estimate": 4_000},
    "perplexity": {"path": "ai_optimization/perplexity/llm_responses/live", "kind": "llm", "model": "sonar",
                   "estimate": 8_000},
    "claude": {"path": "ai_optimization/claude/llm_responses/live", "kind": "llm", "model": "claude-sonnet-5-5",
               "web": True, "estimate": 60_000},
    "gemini": {"path": "ai_optimization/gemini/llm_responses/live", "kind": "llm", "model": "gemini-3.8-flash",
               "web": True, "estimate": 60_000},
}
DEFAULT_ENGINES = ("chatgpt", "ai_mode", "perplexity", "claude", "gemini")     # gemini_app only when named
NO_SEARCHES = {"ai_mode", "gemini_app"}        # these show the pages they cite, never the searches they ran
SAMPLES = {"chatgpt": 2, "perplexity": 2}      # cheap, and their answers vary the most; the others are asked once
MAX_USD = 1.00
WORKERS = 4                     # answers asked at once; each takes 3 to 60 seconds
MAX_TOKENS = 1500               # an answer's length; with web search the models may run past it
SHOWN = 15
SEARCHES_SHOWN = 20
PAGES_KEPT = 50          # pages ranks keeps, the most searches first
REDIRECT = "vertexaisearch.cloud.google.com"   # Gemini cites through Google's redirect: the title names the site
LABEL_MIN = 8                   # your domain's name without its ending counts as a mention from this length: "skills"
                                # (skills.sh) is in every answer about skills, "agentskillshub" only in one about you
WRITERS = {"chatgpt": ("ai_optimization/chat_gpt/llm_responses/live", "gpt-5.4-mini", "ChatGPT"),
           "claude": ("ai_optimization/claude/llm_responses/live", "claude-haiku-5-5", "Claude"),
           "gemini": ("ai_optimization/gemini/llm_responses/live", "gemini-3.5-flash", "Gemini")}
WRITE_ESTIMATE = 10_000
WRITE_MAX_USD = 0.05
RANK_PATHS = {"google": "serp/google/organic/live/regular", "bing": "serp/bing/organic/live/regular"}
RANK_DEPTH = 20                 # results read for each search: the first two pages
RANK_ESTIMATE = 4_000           # micro-USD a search at RANK_DEPTH: $0.0035 on Google and on Bing (2026-10-26)
FIRST_PAGE = 10
ASK_AS = ("You are someone who wants {what}. Write {count} different questions you would type into {assistant} to "
          "find it: short ones and long ones, ones that name tools you already know and ones that do not, ones about a "
          "particular task. Only the questions, one a line, no numbering.")
MD_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\((https?://[^)\s]+)\)")
LISTED = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\*\*(.+?)\*\*", re.M)
QUESTION = re.compile(r"^\s*(?:[-*•]|\d+[.)])?\s*[\"“]?(.+?)[\"”]?\s*$")


# ---------- reading an answer ----------

def cited_page(url: str, title: str) -> dict | None:
    """{"url", "site", "title"}; Gemini's redirect keeps only the site its title names (url "")."""
    title = " ".join(str(title or "").split())
    if not url.startswith(("http://", "https://")):
        return None
    if page.host(url) == REDIRECT:
        site = page.registrable(title.lower()) if "." in title else ""
        return {"url": "", "site": site, "title": title} if site else None
    return {"url": url, "site": page.registrable(url), "title": title}


def pages_of(pairs) -> list[dict]:
    """The pages (url, title) name, each once, in order."""
    found: dict[str, dict] = {}
    for url, title in pairs:
        p = cited_page(url or "", title or "")
        if p:
            found.setdefault(p["url"] or p["site"], p)
    return list(found.values())


def listed_names(markdown: str) -> list[str]:
    """The bold names that open an answer's list items: how an assistant writes up the tools it recommends."""
    return [MD_LINK.sub(r"\1", m).strip(" :`*") for m in LISTED.findall(markdown or "")]


def read_scraper(r: dict) -> dict:
    """ChatGPT's own interface: its sources are what it cited; its search results, what it read."""
    text = r.get("markdown") or ""
    names = [b.get("title") or "" for b in r.get("brand_entities") or []] or listed_names(text)
    return {"text": text, "names": names, "fan_out": r.get("fan_out_queries") or [],
            "cited": pages_of((s.get("url"), s.get("title")) for s in r.get("sources") or []),
            "read": pages_of((s.get("url"), s.get("title")) for s in r.get("search_results") or [])}


def read_serp(r: dict) -> dict:
    """Google's AI Mode: its references and the links in its text."""
    items = r.get("items") or []
    text = "\n".join(i.get("markdown") or "" for i in items)
    found = [(c["url"], c["title"]) for c in cited.citations(items)] + [(u, t) for t, u in MD_LINK.findall(text)]
    return {"text": text, "names": listed_names(text), "fan_out": [], "cited": pages_of(found), "read": []}


def read_llm(r: dict) -> dict:
    """An API answer: its text, the sources it annotated, the searches it ran."""
    sections = [s for i in r.get("items") or [] for s in i.get("sections") or []]
    text = "\n".join(s.get("text") or "" for s in sections)
    notes = ((a.get("url"), a.get("title")) for s in sections for a in s.get("annotations") or [])
    return {"text": text, "names": listed_names(text), "fan_out": r.get("fan_out_queries") or [],
            "cited": pages_of(notes), "read": []}


READ = {"scraper": read_scraper, "serp": read_serp, "llm": read_llm}


def label_of(domain: str) -> str:
    return domain.split(".")[0]


def lookalikes(own: str, sites, text: str = "") -> set[str]:
    """Other sites under your name with another ending (agentskillshub.dev for agentskillshub.top), among the sites
    given and the domains written in the text."""
    label = label_of(own)
    if len(label) < LABEL_MIN:
        return set()
    written = re.findall(rf"\b{re.escape(label)}\.[a-z]{{2,}}(?:\.[a-z]{{2,}})?", text.lower())
    return {s for s in set(sites) | set(written) if label_of(s) == label and s != own}


def named_how(text: str, own: str, names: list[str], others: set[str] = frozenset()) -> str:
    """"domain" when the answer writes your domain; "name" when only your name (or your domain without its ending)
    and no site of the same name is in the answer, since "Agent Skills Hub" is also agentskillshub.dev's name; else ""."""
    low, label = text.lower(), label_of(own)
    if page.domain_in_text(own, low):
        return "domain"
    if others:
        return ""
    by_name = (len(label) >= LABEL_MIN and label in low.replace(" ", "")) or any(n.lower() in low for n in names)
    return "name" if by_name else ""


# ---------- asking ----------

def task(engine: str, question: str) -> dict:
    e = ENGINES[engine]
    if e["kind"] != "llm":
        return {"keyword": question, "location_code": US, "language_code": EN}
    body = {"user_prompt": question, "model_name": e["model"], "max_output_tokens": MAX_TOKENS}
    return body | ({"web_search": True} if e.get("web") else {})


def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval (lower, upper) in [0.0, 1.0] for binomial proportion."""
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denom
    half = (z * ((p * (1.0 - p) + (z * z) / (4.0 * total)) / total) ** 0.5) / denom
    return round(max(0.0, center - half), 3), round(min(1.0, center + half), 3)


def answer(job: tuple[str, str, int], own: str, names: list[str], budget: Budget, fresh: bool) -> dict:
    """One answer as a row; {"left_out": True} when the cap left it out, {"error"} when it failed."""
    engine, question, sample = job
    e, row = ENGINES[engine], {"question": question, "engine": engine, "sample": sample}
    key = f"aisa:asked:{engine}:{e.get('model', '')}:{sample}:{question.lower()}"
    try:
        data, _ = budget.ask(key, e["estimate"], lambda: aisa.rest(e["path"], task(engine, question)), fresh,
                             f"{engine} “{question}”")
    except OverBudget:
        return row | {"left_out": True}
    except aisa.AisaError as exc:
        return row | {"error": str(exc)}
    got = READ[e["kind"]](data or {})
    cited_sites = {p["site"] for p in got["cited"]}
    read_sites = {p["site"] for p in got["read"]}
    sites = cited_sites | read_sites
    others = lookalikes(own, sites, got["text"])
    return row | got | {"named_you": named_how(got["text"], own, names, others),
                        "cited_you": own in cited_sites, "read_you": own in read_sites,
                        "lookalikes": sorted(others)}


def jobs_of(questions: list[str], engines: list[str], samples: int | None) -> list[tuple[str, str, int]]:
    """Every (engine, question, sample), question by question, so a cap cuts whole questions last."""
    return [(e, q, s) for q in questions for e in engines for s in range(samples or SAMPLES.get(e, 1))]


# ---------- the tally ----------

def by_engine(rows: list[dict], engines: list[str]) -> list[dict]:
    out = []
    for engine in engines:
        mine = [r for r in rows if r["engine"] == engine]
        total = len(mine)
        n = total or 1
        cited_n = sum(r["cited_you"] for r in mine)
        named_n = sum(r["named_you"] == "domain" for r in mine)
        read_n = sum(r.get("read_you", False) for r in mine)
        out.append({"engine": engine, "answers": total, "named_you": named_n,
                    "name_only": sum(r["named_you"] == "name" for r in mine), "cited_you": cited_n,
                    "read_you": read_n,
                    "citation_rate": round(cited_n / n, 3) if total else 0.0,
                    "citation_ci": list(wilson_ci(cited_n, total)),
                    "named_rate": round(named_n / n, 3) if total else 0.0,
                    "named_ci": list(wilson_ci(named_n, total)),
                    "lookalike": sum(bool(r["lookalikes"]) for r in mine),
                    "searches": round(sum(len(r["fan_out"]) for r in mine) / n, 1),
                    "cited": round(sum(len(r["cited"]) for r in mine) / n, 1)})
    return out


def distribution_of(rows: list[dict], questions: list[str]) -> dict:
    """Multi-run stability summary across all answers and per question."""
    total = len(rows)
    cited_n = sum(r.get("cited_you", False) for r in rows)
    named_n = sum(bool(r.get("named_you")) for r in rows)
    by_q = []
    for q in questions:
        q_rows = [r for r in rows if r["question"] == q]
        qn = len(q_rows)
        qc = sum(r.get("cited_you", False) for r in q_rows)
        qm = sum(bool(r.get("named_you")) for r in q_rows)
        by_q.append({"question": q, "answers": qn, "cited_you": qc, "named_you": qm,
                     "citation_rate": round(qc / qn, 3) if qn else 0.0,
                     "citation_ci": list(wilson_ci(qc, qn))})
    return {
        "answers": total,
        "cited_you": cited_n,
        "citation_rate": round(cited_n / total, 3) if total else 0.0,
        "citation_ci": list(wilson_ci(cited_n, total)),
        "named_you": named_n,
        "named_rate": round(named_n / total, 3) if total else 0.0,
        "named_ci": list(wilson_ci(named_n, total)),
        "by_question": by_q,
    }


def site_tally(rows: list[dict], own: str) -> list[dict]:
    """Every site an answer cited, the most answers first, with a page cited and what can be done there."""
    by: dict[str, dict] = defaultdict(lambda: {"answers": 0, "engines": set(), "questions": set(), "pages": {}, "fan_out": set()})
    for r in rows:
        for site in dict.fromkeys(p["site"] for p in r["cited"]):
            t = by[site]
            t["answers"] += 1
            t["engines"].add(r["engine"])
            t["questions"].add(r["question"])
            for q in r.get("fan_out") or []:
                t["fan_out"].add(" ".join(str(q).lower().split()))
        for p in r["cited"]:
            by[p["site"]]["pages"].setdefault(p["url"] or f"https://{p['site']}/", p["title"])
    return sorted((site_row(site, t, own) for site, t in by.items()),
                  key=lambda x: (-x["answers"], -len(x["engines"]), -x["coverage_score"], x["site"]))


def site_row(site: str, t: dict, own: str) -> dict:
    url, title = next(iter(t["pages"].items()))
    kind = find.kind_of(url, title)
    fan_out = sorted(t.get("fan_out") or ())
    coverage = len(t["questions"]) * len(t["engines"]) + len(fan_out)
    return {"site": site, "answers": t["answers"], "engines": sorted(t["engines"]), "questions": sorted(t["questions"]),
            "fan_out_hits": len(fan_out), "coverage_score": coverage,
            "urls": list(t["pages"]), "title": title, "you": site == own, "lookalike": bool(lookalikes(own, [site])),
            "kind": kind, "action": find.ACTIONS[kind]}


def incremental_reach(rows: list[dict], own: str) -> list[dict]:
    """Greedy Set Cover (Incremental Reach) ordering of cited third-party sites by how many *uncovered*
    buyer questions each site newly covers (with answer citations and engine breadth as tie-breakers)."""
    all_qs = list(dict.fromkeys(r["question"] for r in rows if r.get("question")))
    total_q = len(all_qs)
    sites = [s for s in site_tally(rows, own) if not s["you"] and not s["lookalike"]]
    uncovered = set(all_qs)
    remaining = list(sites)
    ordered = []
    covered: set[str] = set()
    step = 0
    while remaining:
        best = max(
            remaining,
            key=lambda s: (
                len(set(s["questions"]) & uncovered),
                s["answers"],
                len(s["engines"]),
                s["coverage_score"],
                - sites.index(s),
            ),
        )
        new_qs = sorted(set(best["questions"]) & uncovered, key=all_qs.index)
        if not new_qs:
            break
        step += 1
        uncovered -= set(new_qs)
        covered |= set(new_qs)
        remaining.remove(best)
        ordered.append({
            "rank": step,
            "site": best["site"],
            "new_questions": len(new_qs),
            "new_question_list": new_qs,
            "total_questions_of_site": len(best["questions"]),
            "cumulative_questions": len(covered),
            "total_questions": total_q,
            "cumulative_share": round(len(covered) / total_q, 3) if total_q else 0.0,
            "answers": best["answers"],
            "engines": best["engines"],
            "urls": best["urls"],
            "title": best["title"],
            "kind": best["kind"],
            "action": best["action"],
        })
    return ordered


def page_tally(rows: list[dict]) -> list[dict]:
    """The pages cited by name (not a redirect), the most answers first."""
    by: dict[str, dict] = {}
    for r in rows:
        for p in r["cited"]:
            if p["url"]:
                t = by.setdefault(p["url"], p | {"answers": 0, "engines": set(), "questions": set(), "fan_out": set()})
                t["answers"] += 1
                t["engines"].add(r["engine"])
                t["questions"].add(r["question"])
                for q in r.get("fan_out") or []:
                    t["fan_out"].add(" ".join(str(q).lower().split()))
    out = []
    for t in by.values():
        engines = sorted(t["engines"])
        questions = sorted(t["questions"])
        fan_out = sorted(t["fan_out"])
        out.append({**t, "engines": engines, "questions": questions, "fan_out": fan_out,
                    "fan_out_hits": len(fan_out), "coverage_score": len(questions) * len(engines) + len(fan_out)})
    return sorted(out, key=lambda x: (-x["answers"], -x["coverage_score"], x["url"]))


def search_tally(rows: list[dict]) -> list[dict]:
    """The searches the assistants ran to answer, the most often first (lower case, spaces collapsed)."""
    times, engines = Counter(), defaultdict(set)
    for r in rows:
        for q in r["fan_out"]:
            key = " ".join(str(q).lower().split())
            times[key] += 1
            engines[key].add(r["engine"])
    return [{"query": q, "times": n, "engines": sorted(engines[q])} for q, n in times.most_common()]


def name_tally(rows: list[dict], own: str, names: list[str]) -> list[dict]:
    """The names the answers gave, the most often first; yours only by your domain, or by name when no site of the
    same name turned up in the run."""
    times = Counter(" ".join(n.split()) for r in rows for n in dict.fromkeys(r["names"]) if n.strip())
    others = set().union(*(r["lookalikes"] for r in rows)) if rows else set()
    return [{"name": n, "times": k, "you": bool(named_how(n, own, names, others))} for n, k in times.most_common()]


# ---------- where you rank for their searches ----------

REDIRECT_PATHS = {"google.com": ("/goto", "/url"), "bing.com": ("/ck/",)}


def is_redirect(url: str) -> bool:
    """A search engine's click-through link (google.com/goto?url=…) instead of the result's own address: on 2026-11-09
    every Google result AIsa passed on came as one, so a site counted from it would be google.com."""
    parts = urllib.parse.urlsplit(url)
    paths = REDIRECT_PATHS.get(page.registrable(url), ())
    return any(parts.path.startswith(p) for p in paths)


def unwrapped(item: dict) -> str:
    """The result's own address: the url, or the one a redirect carries in plain text, or "" when it carries none."""
    url = item["url"]
    if not is_redirect(url):
        return url
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    plain = next((v[0] for k in ("url", "q", "u") for v in [q.get(k)] if v and v[0].startswith("http")), "")
    return plain


def from_breadcrumb(item: dict) -> str:
    """The result's address from its breadcrumb ("https://mine.example › docs › skills") when its url is a redirect that
    carries none: since 2026-11-23 every Google result AIsa passes on is an opaque google.com/goto link, its domain field
    says google.com too, and only the breadcrumb still names the site. A social profile's breadcrumb is a follower count
    ("810+ followers"): nothing to read. Google shortens the path, so the site is right and the path approximate."""
    crumb = str(item.get("breadcrumb") or "").strip()
    if not crumb.startswith(("http://", "https://")):
        return ""
    head, *rest = [x.strip() for x in crumb.split("›")]
    return head.rstrip("/") + "".join("/" + x for x in rest if x and x not in ("...", "…"))


def organic(data: dict) -> list[dict]:
    """[{"url", "site", "position"}]: the organic results of a results page, in order. A redirect whose address cannot
    be read, from the link or from the breadcrumb, keeps its place and is marked, so positions stay true and nothing
    counts it as the search engine's site."""
    found = [i for i in data.get("items") or [] if i.get("type") == "organic" and i.get("url")]
    out = []
    for n, i in enumerate(found, 1):
        url = unwrapped(i) or from_breadcrumb(i)
        out.append({"url": url or i["url"], "site": page.registrable(url) if url else "",
                    "position": i.get("rank_group") or n} | ({} if url else {"redirect": True}))
    return out


def results_for(engine: str, query: str, budget: Budget, fresh: bool) -> list[dict]:
    """One of their searches on Google or Bing (US, English, top RANK_DEPTH). A failed search is asked once more: on
    2026-10-26 AIsa's Google results answered "Internal SE Server Error." to 21 of 67 searches, and 11 came back."""
    body = {"keyword": query, "location_code": US, "language_code": EN, "depth": RANK_DEPTH}

    def fetch():
        try:
            data, cost = aisa.rest(RANK_PATHS[engine], body)
        except aisa.AisaError:
            data, cost = aisa.rest(RANK_PATHS[engine], body)
        return organic(data or {}), cost
    rows, _ = budget.ask(f"aisa:rank:{engine}:{US}:{RANK_DEPTH}:{query}", RANK_ESTIMATE, fetch, fresh,
                         f"{engine} “{query}”")
    return rows


def placed(rows: list[dict], own: str) -> dict:
    """Where you and a site under your name stand in one search's results, and the sites on its first page."""
    hidden = sum(r.get("redirect", False) or is_redirect(r["url"]) for r in rows)
    rows = [r for r in rows if not (r.get("redirect") or is_redirect(r["url"]))]
    mine = next((r for r in rows if r["site"] == own), None)
    alike = lookalikes(own, {r["site"] for r in rows})
    other = next((r for r in rows if r["site"] in alike), None)
    return {"you": mine["position"] if mine else None, "your_page": mine["url"] if mine else "",
            "lookalike": other["position"] if other else None, "lookalike_site": other["site"] if other else "",
            "first_page": list(dict.fromkeys(r["site"] for r in rows if r["position"] <= FIRST_PAGE)),
            "first_page_urls": list(dict.fromkeys(r["url"] for r in rows if r["position"] <= FIRST_PAGE)),
            "redirects": hidden}


BING_NO_SITE = "Bing's results API does not take site:"


def rank_one(job: tuple[str, str], own: str, budget: Budget, fresh: bool) -> dict:
    query, engine = job
    if engine == "bing" and "site:" in query.lower():
        return {"error": BING_NO_SITE}   # it answers an error, and the call is asked twice: don't pay for either
    try:
        return placed(results_for(engine, query, budget, fresh), own)
    except OverBudget:
        return {"left_out": True}
    except aisa.AisaError as exc:
        return {"error": str(exc)}


def rank_by_engine(rows: list[dict]) -> list[dict]:
    out = []
    for engine in RANK_PATHS:
        got = [r[engine] for r in rows]
        read = [g for g in got if "first_page" in g]
        out.append({"engine": engine, "searches": len(read), "you": sum(g["you"] is not None for g in read),
                    "you_first_page": sum(g["you"] is not None and g["you"] <= FIRST_PAGE for g in read),
                    "lookalike": sum(g["lookalike"] is not None for g in read),
                    "redirects": sum(g.get("redirects", 0) for g in read),
                    "failed": sum("error" in g for g in got), "left_out": sum("left_out" in g for g in got)})
    return out


def ranked_sites(rows: list[dict], own: str, cited_sites: list[dict]) -> list[dict]:
    """The sites on the first page of the most searches, with how many answers cited them: ranking without being
    cited was passed over; cited without ranking came from elsewhere (another search, what the model already knew)."""
    cited_in = {s["site"]: s["answers"] for s in cited_sites}
    by: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        for engine in RANK_PATHS:
            for site in r[engine].get("first_page") or []:
                by[site][engine] += 1
    out = [{"site": s, **{e: n[e] for e in RANK_PATHS}, "cited": cited_in.get(s, 0), "you": s == own,
            "lookalike": bool(lookalikes(own, [s]))} for s, n in by.items()]
    return sorted(out, key=lambda x: (-sum(x[e] for e in RANK_PATHS), -x["cited"], x["site"]))


def page_key(url: str) -> str:
    """One page however a search or an answer writes its address: no scheme, www, query, fragment or end slash."""
    parts = urllib.parse.urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    return f"{host}{parts.path.rstrip('/')}"


def ranked_pages(rows: list[dict], own: str, cited_pages: list[dict]) -> list[dict]:
    """The pages on the first page of the most searches, with how many answers cited each: a page that several of
    the assistants' searches return is where to be listed (Michał Rochwerger, CMSEO 2026: one answer's citations are
    a sample, the searches behind it are the pool)."""
    cited_in = {page_key(p["url"]): p["answers"] for p in cited_pages}
    by: dict[str, Counter] = defaultdict(Counter)
    queries_by: dict[str, set[str]] = defaultdict(set)
    assistants_by: dict[str, set[str]] = defaultdict(set)
    first_url: dict[str, str] = {}
    for r in rows:
        for engine in RANK_PATHS:
            for url in r[engine].get("first_page_urls") or []:
                key = page_key(url)
                first_url.setdefault(key, url)
                by[key][engine] += 1
                if r.get("query"):
                    queries_by[key].add(r["query"])
                assistants_by[key].update(r.get("assistants") or ())
    out = []
    for k, n in by.items():
        url = first_url[k]
        searches = sum(n.values())
        cited_n = cited_in.get(k, 0)
        q_hits = len(queries_by[k])
        assts = sorted(assistants_by[k])
        coverage = searches * max(1, len(assts)) + cited_n
        out.append({"url": url, "site": page.registrable(url), **{e: n[e] for e in RANK_PATHS},
                    "searches": searches, "fan_out_queries": q_hits, "assistants": assts,
                    "coverage_score": coverage, "cited": cited_n, "you": page.registrable(url) == own})
    # cited pages first: a page every search returns but no answer cites is often the engine's own (a login page)
    return sorted(out, key=lambda x: (x["cited"] == 0, -x["searches"], -x["cited"], -x["coverage_score"], x["url"]))


def ranks(searches: list[dict], own: str, cited_sites: list[dict], budget: Budget, fresh: bool,
          cited_pages: list[dict] = ()) -> dict:
    """Where you rank on Google and Bing for the searches the assistants ran, the most-run first so that a cap leaves
    out the rarest: {"depth", "searches": [{"query", "times", "assistants", "google", "bing"}], "by_engine", "sites",
    "left_out"}."""
    before = len(budget.left_out)
    jobs = [(s["query"], e) for s in searches for e in RANK_PATHS]
    with ThreadPoolExecutor(WORKERS) as pool:
        got = dict(zip(jobs, pool.map(lambda j: rank_one(j, own, budget, fresh), jobs)))
    rows = [{"query": s["query"], "times": s["times"], "assistants": s["engines"]}
            | {e: got[(s["query"], e)] for e in RANK_PATHS} for s in searches]
    sites = ranked_sites(rows, own, cited_sites)
    ranking = {s["site"] for s in sites}
    return {"depth": RANK_DEPTH, "searches": rows, "by_engine": rank_by_engine(rows), "sites": sites,
             "pages": ranked_pages(rows, own, cited_pages)[:PAGES_KEPT],
            "cited_elsewhere": [{"site": s["site"], "answers": s["answers"]} for s in cited_sites if s["site"] not in ranking],
            "left_out": budget.left_out[before:]}


def asked(domain: str, questions: list[str], names: list[str] = (), engines: list[str] | None = None,
          samples: int | None = None, max_usd: float = MAX_USD, fresh: bool = False, rank: bool = False) -> dict:
    """{"domain", "questions", "answers", "by_engine", "distribution", "sites", "pages", "searches", "named", "cost",
    "max_usd", "left_out", "errors"}, and "ranks" with rank."""
    own, budget, names = page.registrable(page.host(domain)), Budget(max_usd), [n for n in names if n.strip()]
    engines = [e for e in (engines or DEFAULT_ENGINES) if e in ENGINES]
    qs = list(dict.fromkeys(" ".join(q.split()) for q in questions if q.strip()))
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda j: answer(j, own, names, budget, fresh), jobs_of(qs, engines, samples)))
    done = [r for r in rows if "cited" in r]
    out = {"domain": own, "names": names, "questions": qs, "engines": engines, "answers": done,
           "by_engine": by_engine(done, engines), "distribution": distribution_of(done, qs),
           "sites": site_tally(done, own), "incremental_reach": incremental_reach(done, own), "pages": page_tally(done),
           "searches": search_tally(done), "named": name_tally(done, own, names), "cost": budget.spent,
           "max_usd": max_usd, "left_out": list(budget.left_out),
           "errors": [f"{r['engine']} “{r['question']}”: {r['error']}" for r in rows if r.get("error")]}
    if rank:
        out["ranks"] = ranks(out["searches"], own, out["sites"], budget, fresh, out["pages"]) | {"cost": budget.spent - out["cost"]}
        out["cost"] = budget.spent
    return out


def from_file(path: str) -> list[str]:
    """Questions one a line; blank lines and # comments skipped."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [x.strip() for x in lines if x.strip() and not x.lstrip().startswith("#")]


# ---------- step one: the questions ----------

def question_lines(text: str) -> list[str]:
    """The questions in a writer's answer, numbering, bullets and quotes taken off."""
    out = []
    for line in (text or "").splitlines():
        m = QUESTION.match(line)
        q = " ".join(m.group(1).split()) if m else ""
        if len(q) >= 8 and not q.endswith(":"):
            out.append(q)
    return out


def merged(by: dict[str, list[str]]) -> list[str]:
    """The writers' questions taken in turn, each once (case and punctuation ignored)."""
    seen, out = set(), []
    for i in range(max((len(v) for v in by.values()), default=0)):
        for qs in by.values():
            key = re.sub(r"[^0-9a-z]+", " ", qs[i].lower()).strip() if i < len(qs) else ""
            if key and key not in seen:
                seen.add(key)
                out.append(qs[i])
    return out


def write_questions(what: str, count: int = 10, max_usd: float = WRITE_MAX_USD, fresh: bool = False) -> dict:
    """{"what", "by": {writer: [question]}, "questions", "cost", "max_usd", "left_out", "errors"}."""
    budget = Budget(max_usd)
    out = {"what": what, "by": {}, "questions": [], "max_usd": max_usd, "errors": []}
    for writer, (path, model, name) in WRITERS.items():
        body = {"user_prompt": ASK_AS.format(what=what, count=count, assistant=name), "model_name": model,
                "max_output_tokens": 1200}
        try:
            data, _ = budget.ask(f"aisa:questions:{writer}:{model}:{count}:{what.lower()}", WRITE_ESTIMATE,
                                 lambda: aisa.rest(path, body), fresh, writer)
        except OverBudget:
            continue
        except aisa.AisaError as exc:
            out["errors"].append(f"{writer}: {exc}")
            continue
        out["by"][writer] = question_lines(read_llm(data or {})["text"])
    return out | {"questions": merged(out["by"]), "cost": budget.spent, "left_out": budget.left_out}
