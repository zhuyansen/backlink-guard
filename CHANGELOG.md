# Changelog

## 0.9.0 (2026-10-26)

On GitHub; not yet on PyPI.

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
