# backlink-guard

[中文](README.zh-CN.md)

Check a link source **before** you submit your site to it, check the link **after** it goes live, and look at your **own** backlink profile for the patterns Google calls link spam.

Most backlink tools help you send more. This one tells you where not to send, and when to slow down.

```bash
python -m backlink_guard vet mcpservers.org turbo0.com navi.tools
```

| Site | Verdict | Reach | Rating | Visits a month | Spam score | Why |
|---|---|---|---|---|---|---|
| mcpservers.org | ⚠️ caution | high | 71 | 715,667 | 12 | It sells links or posts that pass ranking credit |
| turbo0.com | ⚠️ caution | medium | 81 | 2,218 | 5 | A high rating with almost no visitors; it sells links; it asks for a link back |
| navi.tools | ⛔ avoid | medium | 4.2 | 3,225 | 23 | The domain is parked or for sale |

Every finding comes with the text or the numbers it was read from:

> **turbo0.com** — ⚠️ A high rating with almost no visitors: the rating comes from links, not readers. *rating 81, about 2,218 visits a month.* ⚠️ It asks for a link or badge back as a condition. *"Free $0 … Backlink to our site is required."* (Google: Excessive link exchanges, or requiring a link as part of an arrangement)

## Why

Google's spam updates came in March, June, August and September 2026. "Buying or selling links", "excessive link exchanges", "low-quality directory or bookmark site links" and "using automated programs or services to create links to your site" are all on [Google's list of link spam](https://developers.google.com/search/docs/essentials/spam-policies#link-spam). Directory lists passed around for link building go stale fast and say nothing about any of this.

A verdict here is a set of signals a person can check. It is not Google's judgment: nobody outside Google can tell whether one link is counted, ignored or held against a site. Google ignores most junk links. What the tool is good for is not wasting effort on dead, empty or link-selling sites, and not building the pattern yourself.

## What it checks

| Signal | How | Source | Cost |
|---|---|---|---|
| Dead, or a parked or expired domain | reads the home page | the site | free |
| Sells followed links or posts | a price next to "dofollow", "guest post", "link insertion" on the home, submit and pricing pages | the site | free |
| Asks for a link or badge back | the same pages | the site | free |
| Links out to gambling, adult, loan or essay-mill sites | outbound links on the home page | the site | free |
| First seen | the Wayback Machine's first copy | archive.org | free |
| Rating | domain rating | GoAnyAPI | $0.002 |
| Reach, and a fall in visits | 12 months of monthly visits; a fall within a month is shown next to the Google updates that ran around it | GoAnyAPI, Google's status feed | $0.004 |
| Whether Google lists it | `site:` search, only for sites with few visitors, asked twice before it counts | GoAnyAPI, then AIsa | $0.004 to $0.01 |
| Spam score of the site's own backlinks | DataForSEO, one call for the batch | AIsa | $0.025 a batch |

For your own domain (`audit`): totals and how many referring domains pass ranking credit (GoAnyAPI), new and lost referring domains by week and the anchors (AIsa), and the spam score of the sites linking to you.

Prices are what the calls cost on 2026-10-13. Paid answers are cached for 7 days.

## Tried on 31 sites (2026-10-13)

Both keys set; the whole run cost about $0.30. The raw rows with their evidence are in [docs/validation-2026-10-13.json](docs/validation-2026-10-13.json).
**Well-known directories and communities**

| Site | Verdict | Reach | Rating | Visits a month | Spam score | Flags |
|---|---|---|---|---|---|---|
| producthunt.com | ✅ ok | high | 91 | 4,339,954 | 6 | – |
| alternativeto.net | ✅ ok | high | 81 | 2,198,818 | 12 | – |
| dev.to | ✅ ok | high | 91 | 5,062,281 | 11 | – |
| libhunt.com | ✅ ok | high | 66 | 254,394 | 27 | – |
| saashub.com | ✅ ok | high | 80 | 395,908 | 7 | – |
| futurepedia.io | ✅ ok | high | 73 | 439,710 | 28 | – |
| theresanaiforthat.com | ✅ ok | high | 78 | 4,418,962 | 8 | – |
| glama.ai | ✅ ok | high | 76 | 252,499 | 4 | – |
| pulsemcp.com | ✅ ok | high | 72 | 175,498 | 5 | – |
| skills.sh | ✅ ok | high | 82 | 2,425,525 | 2 | – |

**MCP and skills directories**

| Site | Verdict | Reach | Rating | Visits a month | Spam score | Flags |
|---|---|---|---|---|---|---|
| mcpservers.org | ⚠️ caution | high | 71 | 715,667 | 12 | paid_follow |
| mcp.so | ⚠️ caution | high | 73 | 320,876 | 6 | paid_follow |
| mcpmarket.com | ⚠️ caution | high | 62 | 1,572,277 | 40 | spam_score |
| mcp.directory | ⚠️ caution | medium | 39 | 74,306 | 25 | traffic_cliff |
| agentskill.sh | ⚠️ caution | medium | 48 | 5,647 | 8 | traffic_cliff |
| skillsmp.com | ✅ ok | high | 68 | 620,591 | 19 | – |
| skillget.dev | ⚠️ caution | low | 0.1 | 0 | 60 | spam_score |

**AI tool directories and launch sites**

| Site | Verdict | Reach | Rating | Visits a month | Spam score | Flags |
|---|---|---|---|---|---|---|
| toolify.ai | ✅ ok | high | 72 | 1,051,842 | 26 | – |
| aibase.com | ⚠️ caution | high | 72 | 547,080 | 49 | spam_score |
| creati.ai | ⚠️ caution | high | 51 | 271,011 | 54 | paid_follow, traffic_cliff, spam_score |
| aitoolnet.com | ⚠️ caution | medium | 56 | 77,458 | 6 | paid_follow, traffic_cliff |
| topai.tools | ⚠️ caution | high | 64 | 506,723 | 46 | traffic_cliff, spam_score |
| turbo0.com | ⚠️ caution | medium | 81 | 2,218 | 5 | paid_follow, link_exchange, hollow_rating |
| navi.tools | ⛔ avoid | medium | 4.2 | 3,225 | 23 | parked, traffic_cliff |
| claw123.com | ⚠️ caution | medium | 3.6 | 3,135 | 53 | traffic_cliff, spam_score |
| clawhomepage.com | ✅ ok | low | 16 | 55 | 16 | – |

**Media sites that publish contributed posts**

| Site | Verdict | Reach | Rating | Visits a month | Spam score | Flags |
|---|---|---|---|---|---|---|
| programminginsider.com | ⚠️ caution | medium | 71 | 95,888 | 23 | traffic_cliff |
| nerdbot.com | ✅ ok | high | 70 | 154,161 | 33 | – |
| thedatascientist.com | ⚠️ caution | medium | 64 | 64,386 | 33 | paid_follow, traffic_cliff |
| techbullion.com | ✅ ok | high | 81 | 158,467 | 9 | – |
| aijourn.com | ⚠️ caution | high | 78 | 281,191 | 20 | traffic_cliff |

What this showed:

- **The ten well-known sites all came back clean.** No false alarm among them, after two fixes the first run forced: dev.to answers an unknown client with HTTP 406 (now "blocked", not "dead"), and a `site:` lookup returned nothing for skills.sh under load (now asked twice, and not asked at all for a site with visitors).
- **Six sites say on their own pages that they sell followed links**, and the evidence quotes them: a $39 review fee with a "Dofollow link (DR 71)", a $1,299 "dofollow placement", a "Do-Follow SEO backlink" at $9.9, "Guest Post / Link Insertion", a two-stage publishing fee.
- **Ten sites lost 46% to 80% of their visits within one month**, in August or September 2026 (the check looks at the last three months), the months of two spam updates. None of the ten well-known sites did: their September was between 74% and 181% of their August. Two cautions. It is a coincidence in time, shown as such. And seven of the ten falls are in the newest month of the data, which estimates like these sometimes revise.
- **One rating meant nothing**: 81, with about 2,200 visits a month.
- **What it cannot see**: of the five media sites that publish contributed posts, one states a fee on its pages. Whether the others charge cannot be read from their sites. A site that sells links in private is not caught by reading it.

## Commands

```bash
python -m backlink_guard vet <site> [more ...] [--free] [--fresh] [--json]
python -m backlink_guard audit <your-domain> [--deep] [--json]
python -m backlink_guard verify <page-url> --to <your-domain>
python -m backlink_guard log add <site> --kind directory --anchor "Your Brand"
python -m backlink_guard log
```

Python 3.10 or newer, standard library only.

- **vet**: about $0.01 a site plus $0.025 for the batch; `--free` reads the sites only.
- **audit**: about $0.06, with `--deep` (full anchor distribution) about $0.10.
- **verify**: free. Verdicts are `followed link`, `qualified link` (nofollow, sponsored or ugc), `redirect only` (through the site's own /go/ page, also when the target is base64-encoded), `not found`, `unreadable`. Only those three rel values hold back credit; `noopener` and `external` do not.
- **log**: your submissions in `state/ledger.jsonl`, with a warning past five a week or when one anchor is used over and over.

## Keys

Both are optional. Without them the page checks still run, and the report says what was not checked.

- **`GOANYAPI_API_KEY`** ([goanyapi.com](https://goanyapi.com/r/ga-95708898fb)): rating, visits, index status, your backlink summary.
- **`AISA_API_KEY`** ([aisa.one](https://go.aisa.one/yansen-zhu)), or `aisa login`: spam scores, weekly new and lost referring domains, anchors.

> Both links are referral links: signing up through them supports this project. The tool works the same with a key from either site directly.

The two overlap on purpose. On the day of the test GoAnyAPI's search endpoints answered 502 all day; the index question went to AIsa instead and the run completed.

## The rules it assumes

From submitting [Agent Skills Hub](https://agentskillshub.top) to directories and lists through 2026:

1. Submit only your own project, only where it fits the list.
2. Read the contribution rules first. Some lists accept humans only.
3. One pull request per list. Never resubmit to push a queue.
4. A handful a week. A hundred directory links in a week is the pattern Google describes.
5. Vary the anchor: brand, bare URL, a plain description.
6. Never pay for a followed link. A paid placement must carry `rel="sponsored"` or `nofollow`.
7. After a listing goes live, check the link. A promise of "dofollow" is often a nofollow or a redirect.

The tool does not submit anything.

## Use it from an agent

```bash
npx skills add zhuyansen/backlink-guard
```

The skill walks an agent through the same order: vet, the rules, verify, audit. It clones this repository to `~/backlink-guard` if it is not there and says the cost before a paid run.

## Limits

- Signals, not verdicts. A fall in visits next to a spam update is a coincidence in time until someone shows otherwise.
- A site that blocks unknown clients gives no page signals; the report says "blocked".
- Links added by script are not seen by `verify`.
- Private link sellers are invisible to it.
- Visit and rating numbers are third-party estimates.
- GoAnyAPI is a young service (first released August 2026). Treat it as an enhancement.

## Thanks

- [Loki Yan @loki_yan_seo](https://x.com/loki_yan_seo), whose notes on the 2026 spam updates ("follow the timeline, then go through the spam policies one by one") set the order this tool works in.
- [饭特稀 | Fentix @fantexi997](https://x.com/fantexi997) for [GoAnyAPI](https://goanyapi.com).

MIT.
