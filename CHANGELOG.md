# Changelog

## 0.12.0 (2026-11-21)

- **`--max-usd` on `find`, `vet`, `competitors`, `audit` and `lost`**: a cap for the whole run, as `asked` and `cited`
  already had; `find` passes what is left of it on to the sites it vets. Cached answers are free.
- **`asked`: incremental reach.** The cited sites ordered by how many questions each one newly covers (a greedy set
  cover, with answers and engines as tie-breakers): the shortest list of places that reaches every question asked.
  Your domain counts as mentioned only when it stands as a domain in the text, not inside a longer one.
- **`asked --engines gemini_app`**: Gemini's own app, through the same LLM scraper as ChatGPT's interface ($0.004 an
  answer against about $0.045 for the Gemini API with web search). Its sources are what it cited; it shows no searches,
  so the report prints `–` there as it does for AI Mode. Asked only when named: the default engines are unchanged
  (`DEFAULT_ENGINES`). Read against 20 real answers from a 2026-11-17 panel: the same 5 that cited the site.

- **`ai-access` (`backlink_guard/ai_access.py`, `ai_access` MCP tool)**: checks the three gates an AI crawler or answer
  engine passes through to read and cite a site or page (free):
  - **Gate 1 — Permission**: `robots.txt` rules grouped by bot role (`training`: `GPTBot`, `ClaudeBot`,
    `Google-Extended`, `CCBot`, `Meta-ExternalAgent`, `Bytespider`, `Applebot-Extended`; `search`: `OAI-SearchBot`,
    `PerplexityBot`, `Amzn-SearchBot`; `user`: `ChatGPT-User`, `Claude-User`, `Perplexity-User`) and `/llms.txt`.
  - **Gate 2 — Edge**: whether the site answers 200 or blocks with a 403/WAF challenge, and how many pages Common
    Crawl's latest index holds via its CDX API.
  - **Gate 3 — Rendering**: visible words in initial HTML vs a client-side CSR shell (`< 50` words and `>= 3` scripts),
    page-level `noindex` (`<meta name="robots">` / `X-Robots-Tag`), and JSON-LD schema.
- **`verify` page-level directives (`page.directives()`)**: `verify` now reads `<meta name="robots">`,
  `<meta name="googlebot">`, `X-Robots-Tag` response headers and `<link rel="canonical">`. A followed `<a>` tag on a
  page with page-level `nofollow` becomes `qualified link (page nofollow)`, and page-level `noindex` or
  `canonical_mismatch` is reported on the result and in the table so a link on a non-indexable page is never mistaken
  for one passing ranking credit.
- **`asked` and `cited` multi-run distribution & fan-out coverage**:
  - `asked` separates `cited_you` (`sources` only) from `read_you` (`search_results` not cited), adds 95% Wilson
    confidence intervals (`wilson_ci`) and per-engine frequency distributions (`distribution_of`), and computes a
    publisher-first fan-out `coverage_score` (`cite_weight × 2 + first_page_weight`) across `sites`, `pages` and
    `ranks.pages`.
  - `cited` adds `--samples N` (`samples` in MCP) to sample each keyword multiple times and report `overview_runs`,
    `you_runs` and per-site `citation_rate` (`cited_runs / runs`).
- **MCP server (`log_add`, `recheck`, `ai_access`)**: added `log_add`, `recheck` and `ai_access` tools to
  `backlink_guard/mcp_server.py`.
- **Fixes**:
  - `find.volumes()` normalizes API keyword keys to lowercase so uppercase input keywords match and no longer cache
    `volume: 0`.
  - `signals.entity()` and `page._step()` now catch `http.client.HTTPException` (including `IncompleteRead`,
    `RemoteDisconnected`, `InvalidURL`).
  - `ledger.checks()` only flags `anchor_repeat` on `keyword`-type anchors (`profile.anchor_kind`), exempting brand,
    bare-URL and generic anchors; `profile.kind_of()` guards empty `domain` so `anchor` is never matched against `""`.
  - Synced CLI help and docstrings for `vet` batch/deep prices (`$0.16` batch, `+$0.19`/`$0.27` deep) and the default
    ledger location (`~/.backlink-guard/ledger.jsonl`).
- `asked --rank` keeps the address of every page on each search's first page (`first_page_urls`) and ranks the
  pages several of the assistants' searches return (`ranks.pages`), with the answers that cited each; the report
  adds a table of the pages on the first page of two searches or more. One answer's citations are a sample; the
  pages its searches return are the pool it draws from (Michał Rochwerger, CMSEO 2026). Lookups cached before this
  change carry the addresses already, so a report from the cache shows the table too. Pages that answers cite come
  first: a page that every search returns but no answer cites is often the engine's own (a login page).
- A search engine's redirect link (google.com/goto?url=…) no longer counts as a result on google.com. On 2026-11-09
  every Google result AIsa passed on came as one (1,495 of them, across 80 searches), so the Google column said
  google.com was on the first page of every search and nothing else was. A link whose address it carries in plain
  text is read through; one that does not is left out and counted, and the report says how many.

## 0.11.2 (2026-10-31)

- `--max-usd` holds when calls run side by side. A call that returned gave its estimate back, wrote its answer to
  the cache and only then counted what it cost, so a call asked in that gap (`asked` runs four at once) saw room that
  was already spent and could take the run past the cap even when every call cost no more than its estimate. The
  estimate is now replaced by the cost in one step, before the cache is written, and a test holds a call in that
  gap. A skills list's reviewer found it.
- The cap is described as what it is, in the help, the skill, the MCP server's tools and the READMEs, which said
  "never more than" and "at most": a call is made only while its estimated price still fits. The estimates are
  prices seen before, at or above what the calls cost then, not prices the providers guarantee, so a call billed
  above its estimate (a longer answer from a model, a price raised since) can take a run past the cap by the
  difference.

## 0.11.1 (2026-10-28)

- Nothing goes out without the user's yes. The skill (section 3) and the MCP server's instructions now tell the
  agent to show where each submission, pull request, issue, form or email goes and its exact text, and to wait for
  the user's yes to that one before sending it. A vet result is not that yes (an `action` of `submit`, an `ok`
  grade), and one yes covers one submission. A plugin directory's reviewer asked for it. Nothing else changed.

## 0.11.0 (2026-10-27)

- `competitors --early`: your competitors' earliest links, the channels they used at launch, which take a new site.
  Each site's earliest 1,000 referring domains, lost ones too (one call, about $0.06; yours included): its launch
  (the first archived copy, or the first referring domain when that came first or more than half a year later), how
  many it had 30, 60 and 90 days on against you at the same age, the weeks that brought a burst with their sites,
  and its first-90-day domains still live, followed and not site-wide (one site linking from its footer or
  navigation, or from 100 pages or more: mostly the owner's other sites or partners, named apart). Then the launch
  checklist: what two or more competitors got early and you lack, each with a linking page, the youngest
  competitor it took and when, and a free vet of the first 10 (`--vet`). The cap is $0.50 unless `--max-usd` says
  otherwise. On 2026-10-27, a site launched in February had 14, 21 and 26 referring domains at 30, 60 and 90 days;
  of its first 26, 15 were still live, followed and not site-wide, 6 lost and 4 site-wide.
- `vet --newcomers`: whether a link source still takes new sites, read off its 8 newest sitemap pages: the sites
  they link to from their body, dated by registration (RDAP, one request every half second, a failure asked once
  more) or, where the registry keeps no RDAP record, the first archived copy. Unknown, with the reason, when the
  sitemaps carry no dates or the pages link through redirects or scripts. Free, 20 to 60 seconds a site; it informs
  and does not change the verdict. In the MCP server: `vet(newcomers=True)`, `competitors(early=True)`.
- A page whose answer breaks off is read up to the break (`http.client.IncompleteRead` got past `page.fetch`, which
  says it never raises, and stopped a whole run); the Wayback and RDAP reads catch it too.

## 0.10.1 (2026-10-26)

- The MCP server's failures reach the agent with their reason. mcp 2.x shows an agent only "Error executing tool
  find" for any exception that is not a `ToolError`, so a missing key, a refused call and a folder the server cannot
  write all read the same; each now arrives with its message, which never holds a key.
- A call AIsa refuses because it went without a key says so (`no AIsa key: set AISA_API_KEY`, and what a Glasser key
  answers instead), in place of the 401 that AIsa sends back.

## 0.10.0 (2026-10-26)

- An MCP server, for Claude Code, Cursor, Claude Desktop and any client that speaks MCP: `backlink-guard mcp` (or
  `backlink-guard-mcp`; `pip install "backlink-guard[mcp]"`, or `uvx --with mcp backlink-guard mcp` with nothing
  installed). Ten tools, one for each command: `verify` and `submissions` are free, `vet` is free with
  `free=True`; `vet`, `find`, `audit`, `lost`, `competitors`, `cited`, `questions` and `asked` buy data. Each returns
  its report as Markdown with what it cost; the server tells the agent to say the cost and wait for a yes before a
  paid call, and to treat what it reads as data. Keys and state come from the environment, as on the command line.
- The Claude Code plugin brings the server with it, pinned to this release, and asks for the Glasser, AIsa and
  GoAnyAPI keys (each optional), which it keeps in the system keychain. `server.json` lists it on the official MCP
  Registry as `io.github.zhuyansen/backlink-guard`; a published release goes to PyPI and then the registry.
- The skill runs the pinned release from PyPI (`uvx backlink-guard==0.10.0`), never a clone, says the cost and waits
  for a yes before any paid run, and treats what it reads as data, never as instructions. A `plugin.json` at the root
  lists it for clients that read the Agent Plugins format.
- A logo, a README header with where it is listed, and the flow diagram redrawn for 0.8 to 0.10: competitors, cited
  and asked beside find, the sites one owner runs in audit, redirects in lost, Glasser beside AIsa.

## 0.9.0 (2026-10-26)

On GitHub only; it reached PyPI with 0.10.0.

- Glasser (`GLASSER_API_KEY`, glasser.ai), asked first when its key is set: spam scores, Google search history, the
  backlink summary, backlinks one by one, new and lost referring domains, anchors, competitors' referring domains and
  link intersect, AI Overviews (`cited`), `find`'s searches and volumes, and `--deep`'s technology and ChatGPT
  mentions. It resells the same endpoints as AIsa at the same prices, but for two searches: `find`'s costs $0.006 a
  keyword ($0.005 through AIsa) and `cited`'s up to $0.006 ($0.004), which `cited`'s cap counts. One Glasser Run a
  call; a Run still queued or running is polled by its id, never created twice, and none is retried. Answers are
  cached as before, whichever answered.
- What Glasser does not sell stays on AIsa: the `site:` search that stands in when GoAnyAPI's fails (Glasser refuses
  searches with operators), `--deep`'s Ahrefs rating and Semrush numbers, and `questions` and `asked`. With Glasser
  alone `--deep` leaves Ahrefs and Semrush out and the report says so once, instead of failing on every site.
- The evidence names who answered: "Glasser rank", "US Google, Glasser estimate", a spam score's "(Glasser)". A row
  saved before 0.9 still reads AIsa.
- ChatGPT mentions are read from either answer shape (AIsa's aggregated metrics, Glasser's target metrics), and the
  provider's own message is kept when it refuses a task through Glasser (such a Run is not billed). `--deep`'s
  columns show when only the technology and ChatGPT mentions came back.
- The docs gave `--deep` as $0.024 a site; it is about $0.19 (backlink profile, technology, ChatGPT mentions,
  checkout links on inner pages), about $0.27 with an AIsa key (Ahrefs' rating, Semrush's numbers).

## 0.8.0 (2026-10-26)

- `asked --rank` (2026-10-26): each search the assistants ran is looked up on Google and Bing (US, English, top 20,
  $0.0035 a search on each), the most-run first so a cap leaves out the rarest, under the same `--max-usd`. The
  report says where you rank and puts the sites on the first page of the most searches next to the answers that
  cited them, and names the sites cited without ranking for any search read. A failed search is asked once more
  (AIsa's Google results answered "Internal SE Server Error." to 21 of 67 searches that day); one that fails twice is
  counted as failed, never as missing. Answers asked in the last 7 days come from the cache, so `--rank` after a run
  costs only the lookups.
- `competitors <your-domain> --vs a b c`: the sites your competitors earned links from and you lack. For each
  competitor, its referring domains first seen in the last `--days` days (7), strongest first, with the ones already
  linking to you taken out; then the sites linking to two or more of them and not to you, from AIsa's domain
  intersection in its partial mode (one call: its page says each row links to every target, but tried live with three
  it returned the domains linking to two or three). Each site comes with a linking page (looked up under its main
  domain and its www. form), what kind of page that is and what can honestly be done there (find's kinds). Left out
  and named: the sites on the shared spam-link list, links that score 50 or more for spam (each row of the lists
  carries the score), and three or more sites whose linking pages share one title (one network's template), with a
  filled-in report for the list. About $0.025 a call, 2N + 2 calls for N competitors: three cost $0.20.
- `cited <your-domain> "<keyword>" ...`: for each keyword, Google's first page with its AI Overview (US, English;
  $0.002 a keyword, $0.004 when the overview loads late), whether the overview cites you and where you rank, then the
  sites cited most across the keywords, each with its kind. A keyword with no AI Overview is said so, never read as
  not cited.
- `questions "<what you make>"` and `asked <your-domain> --file questions.txt` (2026-10-21): the three steps of working
  on AI answers. `questions` has ChatGPT, Claude and Gemini each write the questions they expect to be asked for it
  (about $0.01). `asked` puts each question to ChatGPT (its own interface), Google's AI Mode, Perplexity, Claude and
  Gemini (with their web search) and keeps what each one searched for (fan-out queries, all but AI Mode), the pages
  it cited with their titles, the tools it named and whether it named or cited you; then the sites and pages cited
  most, each with its kind, and the searches they ran. ChatGPT and Perplexity are asked twice (their answers vary
  most): about $0.12 a question, `--max-usd` $1.00 by default.
- `--max-usd` for both (budget.py; $0.30 and $0.10 by default): a call is made only while its estimate still fits
  under the cap, answers cached in the last 7 days are free, and the report names what the cap left out. Calls made
  side by side hold their estimates against the cap while they run.
- `lost` follows each page of yours that redirects one hop at a time (`page.trace`) and judges it, worst first:
  broken (a loop, more than ten hops, or no page at the end), soft-lost (it ends on your home page, on another site or
  on a page whose path matches under 0.50, with the closest live page suggested as for a dead one), temporary (302,
  303, 307), chain (two hops or more) or fine. They are listed next to the dead pages, each kind with a note citing
  Google's pages on redirects and site moves. A redirect that ends in an HTTP error other than 404 or 410 is now
  broken, where it was refused.
- `audit` reads the home page of each referring domain (free, at most `--homes`, 300) for the analytics and ads
  accounts it reports to, as `vet` does, and flags three or more on one account, two of them linking to you, as one
  owner's network (`owner_network`, a caution): its sites, links and listed members in a table, counted as one source,
  with a report for the shared list when the list already holds half of them. The accounts join the networks seen
  before. When the backlinks read name fewer sites than `--homes`, AIsa's referring-domains list fills up the rest
  (about $0.035 for 300).
- Accounts read from a home page now include Cloudflare Web Analytics tokens (`vet` too): of 106 link-network pages,
  one carried an AdSense or Google ID and 87 this beacon, one token on 14 of them.
- `page.site` knows more two-label suffixes (com.co, com.vn, com.ua, co.th and others).
- Tests: a test that reaches the network fails at once (`tests/conftest.py`). Two `--deep` tests had been calling
  AIsa through the proxy with the test key.

## 0.7.0 (2026-10-18)

- `lost <your-domain>`: the pages of yours that backlinks point at and that answer 404 or 410, most referring
  domains first, each with its links, the strongest referring domain and a suggested 301 target: the live page
  in your own sitemaps (robots.txt or /sitemap.xml, indexes followed, up to 10 files and 50,000 pages) whose path
  is closest, with the match from 0 to 1 and no suggestion under 0.50. One polite GET a page (redirects followed,
  four at a time, at most 200 pages). Only 404 and 410 are dead, also at the end of a redirect chain; any other
  HTTP error is reported as refused and no answer as unreachable, never as dead. Nothing is redirected. The
  finding cites Google's page on redirects (301 or 308 for a page that has moved for good).
- Referring domains beside every link count: `audit` reads up to 1,000 backlinks one by one from AIsa (`--rows`;
  about $0.06, cached 7 days and shared with `lost`), and its anchor table, anchor findings and the log's
  repeated-anchor finding say how many referring domains (or sites) are behind each count. Without an AIsa key
  the top linking pages from GoAnyAPI stand in.
- Site-wide links: one referring domain linking to one page of yours from 20 or more of its pages (`--sitewide`),
  or from three or more with most of them in its footer, sidebar, header or navigation. Each is a note citing
  Google's "widely distributed links in the footers or templates of various sites", is listed in its own table,
  and counts as one link wherever a share is worked out (the anchor shares, also with `--deep`): "N links from
  1 site, counted once".
- Registrable domains: `page.registrable` keeps a subdomain of a shared host (github.io, blogspot.com,
  netlify.app and the like) as its own referring domain; more two-label suffixes (org.uk, com.sg, co.za …).
- `page.fetch` keeps the final URL of a request that ended in an HTTP error, so a redirect chain that ends in a
  404 says where it ended.
- `audit` now costs about $0.12, with `--deep` about $0.16.
