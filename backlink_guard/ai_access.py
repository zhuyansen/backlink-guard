"""AI Accessibility three-gate check: can AI search crawlers and assistants actually read and cite a site?

Three gates (Jes Scholz / Gianluca Fiorelli, CMSEO 2026):
  1. Permission gate (robots.txt + llms.txt): separates training crawlers (GPTBot, ClaudeBot, Google-Extended, CCBot),
     AI search crawlers (OAI-SearchBot, PerplexityBot, Applebot-Extended), and user-triggered fetchers (ChatGPT-User,
     Claude-Web, Perplexity-User). Blocking training crawlers is a choice; blocking search or user fetchers keeps the
     site out of AI answers.
  2. Edge & index gate (HTTP/WAF + Common Crawl): checks whether edge WAF/CDN returns 403/429/Cloudflare challenge to
     non-browser requests and whether Common Crawl's CDX index holds snapshots of the domain.
  3. Rendering & directives gate (raw HTML): checks whether initial HTML without JavaScript execution carries real body
     text (not an empty CSR shell like <div id="root"></div>), whether meta robots / X-Robots-Tag blocks indexing, and
     whether JSON-LD structured data is present.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

from . import UA, cache, page

COMMON_CRAWL_INDEX = "https://index.commoncrawl.org/CC-MAIN-2026-13-index"

BOT_CLASSES: dict[str, tuple[str, ...]] = {
    "training": ("GPTBot", "ClaudeBot", "Google-Extended", "CCBot"),
    "search": ("OAI-SearchBot", "PerplexityBot", "Applebot-Extended"),
    "user": ("ChatGPT-User", "Claude-Web", "Perplexity-User"),
}


def parse_robots(text: str) -> dict:
    """Parse robots.txt and return per-bot status ('allowed' or 'blocked') and grouped summary by class."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    current_agents: list[str] = []
    current_rules: list[tuple[str, str]] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = [x.strip() for x in line.split(":", 1)]
        low_key = key.lower()
        if low_key == "user-agent":
            if current_rules:
                groups.append((current_agents, current_rules))
                current_agents, current_rules = [], []
            current_agents.append(val.lower())
        elif low_key in ("disallow", "allow") and current_agents:
            current_rules.append((low_key, val))
    if current_agents:
        groups.append((current_agents, current_rules))

    def _is_blocked(bot: str) -> bool:
        target = bot.lower()
        specific = [rules for agents, rules in groups if target in agents]
        wildcard = [rules for agents, rules in groups if "*" in agents]
        matched = specific if specific else wildcard
        if not matched:
            return False
        rules = [r for grp in matched for r in grp]
        disallowed_root = any(kind == "disallow" and path.strip() == "/" for kind, path in rules)
        allowed_root = any(kind == "allow" and path.strip() in ("/", "/*") for kind, path in rules)
        return disallowed_root and not allowed_root

    bots: dict[str, dict[str, str]] = {}
    blocked_classes: dict[str, list[str]] = {}
    for cls, names in BOT_CLASSES.items():
        cls_map: dict[str, str] = {}
        for b in names:
            state = "blocked" if _is_blocked(b) else "allowed"
            cls_map[b] = state
        bots[cls] = cls_map
        blocked_classes[cls] = [b for b, st in cls_map.items() if st == "blocked"]
    return {"bots": bots, "blocked": blocked_classes}


def common_crawl_count(domain: str, fresh: bool = False) -> int | None:
    """Number of sampled URLs in Common Crawl CDX index (up to 20), or None when unreachable."""
    key = f"cc:{domain}"
    if not fresh and (hit := cache.get(key)) is not None:
        return hit
    q = urllib.parse.urlencode({"url": f"{domain}/*", "output": "json", "limit": "20"})
    req = urllib.request.Request(f"{COMMON_CRAWL_INDEX}?{q}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            lines = [ln for ln in res.read(100_000).decode("utf-8", "replace").splitlines() if ln.strip()]
            cache.put(key, len(lines))
            return len(lines)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            cache.put(key, 0)
            return 0
        return None
    except Exception:
        return None


def check(url_or_domain: str, check_cc: bool = True, fresh: bool = False) -> dict:
    """Run the 3-gate AI accessibility check on a URL or domain (free)."""
    url = url_or_domain if url_or_domain.startswith(("http://", "https://")) else f"https://{url_or_domain.strip('/')}/"
    domain = page.registrable(url)
    origin = f"https://{page.host(url)}"

    home = page.fetch(url)
    robots_res = page.fetch(f"{origin}/robots.txt")
    llms_res = page.fetch(f"{origin}/llms.txt")

    robots_txt = robots_res["html"] if robots_res["status"] == 200 and not robots_res["dead"] else ""
    parsed_robots = parse_robots(robots_txt)
    has_llms_txt = llms_res["status"] == 200 and not llms_res["dead"] and len((llms_res["html"] or "").strip()) > 10

    dirs = page.directives(home["html"], home["final"], home.get("headers"))
    cc_count = common_crawl_count(domain, fresh=fresh) if check_cc else None

    issues: list[str] = []
    if parsed_robots["blocked"]["search"]:
        issues.append(f"robots.txt blocks AI search crawlers ({', '.join(parsed_robots['blocked']['search'])})")
    if parsed_robots["blocked"]["user"]:
        issues.append(f"robots.txt blocks user-triggered AI fetchers ({', '.join(parsed_robots['blocked']['user'])})")
    if home["blocked"] or home["status"] in (401, 403, 406, 429, 503):
        issues.append(f"edge/WAF blocked HTTP request ({home['error'] or home['status']})")
    elif home["dead"]:
        issues.append(f"page unreachable ({home['error'] or home['status']})")
    if dirs["noindex"]:
        issues.append("page carries noindex directive")
    if dirs["csr_shell"]:
        issues.append(f"initial HTML is an empty CSR shell ({dirs['words']} words, {dirs['scripts']} scripts): non-JS AI crawlers see nothing")

    if home["blocked"] or home["dead"] or dirs["noindex"] or dirs["csr_shell"] or (
        len(parsed_robots["blocked"]["search"]) == len(BOT_CLASSES["search"])
    ):
        verdict = "blocked"
    elif issues or parsed_robots["blocked"]["training"] or cc_count == 0:
        verdict = "caution"
    else:
        verdict = "ok"

    return {
        "url": url,
        "domain": domain,
        "verdict": verdict,
        "permission": {
            "robots_status": robots_res["status"],
            "bots": parsed_robots["bots"],
            "blocked": parsed_robots["blocked"],
            "llms_txt": has_llms_txt,
        },
        "edge": {
            "status": home["status"],
            "blocked": home["blocked"],
            "dead": home["dead"],
            "error": home["error"],
            "common_crawl_pages": cc_count,
        },
        "rendering": dirs,
        "issues": issues,
        "cost": 0,
        "errors": [],
    }
