# backlink-guard

[中文](https://github.com/zhuyansen/backlink-guard/blob/main/README.zh-CN.md)

Find the pages your searchers already land on, check a link source **before** you submit your site to it, check the link **after** it goes live, and look at your **own** backlink profile for the patterns Google calls link spam.

Most backlink tools help you send more. This one tells you where not to send, and when to slow down.

![How backlink-guard works: find the pages your searchers land on, vet each site (its own pages, GoAnyAPI, AIsa), get avoid, caution or ok with the evidence, follow the rules, submit, then verify and log; audit your own profile now and then](https://raw.githubusercontent.com/zhuyansen/backlink-guard/main/docs/flow.en.gif)

## Quick start

```bash
pip install "git+https://github.com/zhuyansen/backlink-guard"
backlink-guard vet mcpservers.org turbo0.com navi.tools producthunt.com clawhomepage.com
```

Python 3.10 or newer, no dependencies; `uvx --from git+https://github.com/zhuyansen/backlink-guard backlink-guard vet …` runs it without installing. With no key it reads the sites' own pages, for free (`--free` asks for just that). The [two keys](#keys) add rating, visits, Google's index and spam scores: about $0.17 for one site and $0.46 for thirty, so check the sites you are considering in one run.

Checked with both keys on 2026-10-13 and 14:

| Site | Action | Verdict | Risk | Link policy | Value | Rating | Visits a month | Spam score | Why |
|---|---|---|---|---|---|---|---|---|---|
| mcpservers.org | 🆓 free only | ✅ ok | 1 | ⚠️ sells followed links | high | 71 | 715,667 | 12 | – |
| turbo0.com | 🆓 free only | ⚠️ caution | 4 | ⚠️ sells followed links; asks for a link back | medium | 81 | 2,218 | 5 | A high rating with almost no visitors: the rating comes from links, not readers; It lost most of its Google search traffic in the last year and has not won it back |
| navi.tools | ⛔ skip | ⛔ avoid | 3 | – | none | – | – | – | The domain is parked or for sale |
| producthunt.com | ✅ submit | ✅ ok | 0 | – | high | 91 | 4,339,954 | 6 | – |
| clawhomepage.com | 💤 low value | ✅ ok | 0 | – | low | 16 | 55 | 16 | – |

**Action** is what to do with the site: skip, look first, free only, low value or submit. It reads three answers that are also shown apart. **Link policy**: what a link there would mean under Google's link spam policies, one finding being enough; mcpservers.org sells followed links, so list there for free and never pay. **Value**: what a listing can bring, which is the site's reach, or none when nobody can reach it (dead, parked, dropped by Google, a shortener, a network page). The **verdict** weighs every finding: one avoid finding makes avoid, and caution takes two caution findings. Risk is 3 for each avoid finding and 1 for each caution. A site its own pages put at avoid, like navi.tools, gets no paid check.

Every finding comes with the text or the numbers it was read from:

> **turbo0.com** — ⚠️ A high rating with almost no visitors: the rating comes from links, not readers. *rating 81, about 2,218 visits a month.* ⚠️ It asks for a link or badge back as a condition. *"Free $0 … Backlink to our site is required."* (Google: Excessive link exchanges, or requiring a link as part of an arrangement)

Sites that share a page template or an analytics or ads account, with each other or with sites from an earlier check on the same machine, are flagged as one operator's. When most of them have something else against them and the [shared spam-link list](https://github.com/zhuyansen/backlink-spam-list) lacks them, the report ends with a link to a filled-in report for that list; nothing is sent until you submit it.

## How well it works

The rules were chosen on 100 sites they had never seen (2026-10-16): 40 that Ahrefs marks SPAM and 60 it does not.

| | 0.4.1 rules | 0.6 |
|---|---|---|
| SPAM sites flagged | 38 of 40 | 28 of 40 |
| Normal sites flagged | 46 of 60 | 21 of 60 |
| SPAM sites with the action "submit" | – | 3 of 40 |

- Every normal-labelled site called avoid does not load or has no pages in Google.
- Of 16 sites around shared checkout links, all 10 network or hacked sites come out skip, and 5 of the 6 that merely cite those products come out submit.
- What a listing brings follows reach: on two sites' analytics, 2 of 37 and 1 of 73 referring domains rated low had sent a visit, against 10 of 14 and 2 of 7 rated high.
- The ten well-known directories and communities all come out submit.

Nine tests, with their data and what each changed: [docs/validation.md](https://github.com/zhuyansen/backlink-guard/blob/main/docs/validation.md).

## Where to be: find

A link is first a way in for visitors. A page that ranks for your keyword already gets the people looking for what you make, so a mention there is the most relevant link there is.

```bash
python -m backlink_guard find "claude skills" "claude code skills" "agent skills" --site agentskillshub.top
```

| Keyword | Searches a month (US) | Difficulty |
|---|---|---|
| claude skills | 40,500 | 27 |
| claude code skills | 12,100 | 30 |
| agent skills | 8,100 | 38 |

| Page | Kind | Ranks | Visitors from these searches | What to do |
|---|---|---|---|---|
| The Claude "Skills" Feature (medium.com) | article | #3 claude skills; #1 claude code skills | about 7,795 | Offer the author what the page lacks |
| Claude can now use Skills (r/ClaudeAI) | community | #2 claude skills | about 6,399 | Answer where it helps; the visitors are the value |
| addyosmani/agent-skills (GitHub) | repo | #1 agent skills | about 2,236 | An integration or a pull request, not a link request |
| Best Claude Skills in 2026 (opxskills.com) | list | #10 claude skills | about 972 | Ask to be added |
| ClaudeSkills, the curated library (claudeskills.com) | directory | #8 claude code skills | about 399 | Submit, after `vet` says it is worth it |
| agent-skills · GitHub Topics | directory | #9 agent skills | about 219 | Add the `agent-skills` topic to your repository |

Three keywords, 30 results each: $0.027 on 2026-10-14. Visitors are monthly searches times the share of clicks a position usually gets, a size and not a count. `--vet` then vets the directories and article sites it found; pages on GitHub, Medium, YouTube or Reddit are judged by the page and its author, not the platform.

## Why

Google's spam updates came in March, June, August and September 2026. "Buying or selling links", "excessive link exchanges", "low-quality directory or bookmark site links" and "using automated programs or services to create links to your site" are all on [Google's list of link spam](https://developers.google.com/search/docs/essentials/spam-policies#link-spam). Directory lists passed around for link building go stale fast and say nothing about any of this.

A verdict here is a set of signals a person can check. It is not Google's judgment: nobody outside Google can tell whether one link is counted, ignored or held against a site. Google ignores most junk links. What the tool is good for is not wasting effort on dead, empty or link-selling sites, and not building the pattern yourself.

## What it checks

| Signal | How | Source | Cost |
|---|---|---|---|
| `find`: the pages that rank for your keywords, by the visitors they get from those searches, and what kind each is | Google's top 30 for each keyword, and its monthly searches | AIsa | $0.005 a keyword, plus $0.012 |
| `--topic`: where a site ranks for your keyword, and whether its pages write about it | the same search; the site's pages | AIsa, the site | $0.005 a keyword |
| Dead, or a parked or expired domain | reads the home page; one that gives no answer at all is asked again 5 seconds later | the site | free |
| Sells followed links or posts | a price next to "dofollow", "guest post", "link insertion" on the home, submit and pricing pages | the site | free |
| Pages that invite guest or sponsored posts (a note), found even when the home page does not link to them | Google search for its "write for us" and guidelines pages | GoAnyAPI | $0.002 |
| Asks for a link or badge back | the same pages | the site | free |
| Links out to gambling, adult, loan or essay-mill sites | outbound links on the home page | the site | free |
| A URL shortener, or a link network's template page ("<domain> \| Keyword Rankings") | the page title | the site | free |
| Several sites sharing one page template, in this check or an earlier one on this machine | the titles with each site's own name taken out (block pages and platform defaults left out) | the batch, earlier checks | free |
| Several sites reporting to one analytics or ads account (AdSense, Google Analytics, Tag Manager, Clarity, Facebook pixel), in this check or an earlier one: one operator | the home page | the batch, earlier checks | free |
| First seen | the Wayback Machine's first copy | archive.org | free |
| A lapsed domain picked up again: archived a year or more before its current registration, registered in the last three years, under 100,000 visits a month | the first copy against the registration date the visits answer carries | archive.org, GoAnyAPI | free with the visits |
| Rating, and a rating with no readers behind it (30 or more, under 5,000 visits a month) | domain rating | GoAnyAPI | $0.002 |
| Reach, and a fall in visits | 12 months of monthly visits; a fall within a month counts once a later month shows it has not come back (in the newest month it is a note), and is shown next to the Google updates that ran around it | GoAnyAPI, Google's status feed | $0.004 |
| Lost its Google search traffic and has not won it back, back to 2022 (a caution within the last year, a note before that) | monthly US Google traffic and ranking keywords; a fall counts when both fall and stay down two months, measured against twelve large sites read in the same call; shown next to the Google updates around it | AIsa, Google's status page | $0.12 a batch plus $0.0012 a site |
| Whether Google lists it | `site:` search, only for sites with few visitors; an empty answer is asked twice before it counts, and a search that fails on both sources is asked once more, never read as empty | GoAnyAPI, then AIsa | $0.004 to $0.01 |
| Spam score of the site's own backlinks, counted from 50 | one call for the batch | AIsa | $0.025 a batch |
| On the shared list of sites that build or sell spam backlinks, each with public evidence ([backlink-spam-list](https://github.com/zhuyansen/backlink-spam-list)) | the list, read once a run and kept a day; a listed site gets no paid check | GitHub | free |
| Sells links as its business ("PBN", "DR/DA" packages) | the page title | the site | free |
| Thousands of pages, almost none ranking: scaled, low-value content (sites in English) | pages in the site's own sitemaps (read up to 1.5 MB a file, so a floor) against the keywords it ranks for on US Google | the site; AIsa | free with the search history |
| `--deep`: a badge network (hundreds of links from each listed site, most in footers, nearly all followed; not read on a site with 100,000 visits a month or more), or an unproven site (under a year old, under 100 linking sites, under 1,000 visits) | backlink summary | AIsa | $0.024 a site |
| A checkout link it carries (Stripe, Gumroad, Lemon Squeezy, Polar, Creem, Dodo, Paddle) also sits on dozens of sites built like it: a network selling links through it, or a gambling or adult product injected into hacked sites. Its seller and the sites that merely cite it are not flagged. `--deep` also finds the checkout links on its inner pages, where networks put them | backlinks, plus the other sites' home pages for their titles | AIsa | about $0.02 a checkout link; with `--deep` about $0.05 more a site |
| `--recent`: whether Google takes in the pages it keeps adding | `site:` search for the last week and month, each zero asked twice, checked against the site's own sitemap | GoAnyAPI | $0.008 a site |

For your own domain (`audit`): totals and how many referring domains pass ranking credit (GoAnyAPI), new and lost referring domains by week and the anchors (AIsa), and the spam score of the sites linking to you.

Prices are what the calls cost on 2026-10-13 and 14. Paid answers are cached for 7 days.

A site its own pages already put at avoid (dead, parked, a URL shortener, a network template page, a link seller, links out to gambling sites) gets no paid check: the rest could only add to it. A site that does not load gets one question, its visits, since a site people visit that refuses the check is blocked, not dead. An ok whose check failed where it could have found something (rating, visits, index, backlink profile, checkout links, spam score, search history) is marked incomplete: run it again before relying on it.

## Commands

```bash
backlink-guard find "<keyword>" [more ...] [--site yoursite.com] [--skip competitors.txt] [--vet] [--json]
backlink-guard vet <site> [more ...] [--from list.xlsx] [--skip yoursite.com] [--limit 30] [--topic "keyword"] [--referrals ga4.csv] [--deep] [--recent] [--free] [--fresh] [--json]
backlink-guard audit <your-domain> [--deep] [--json]
backlink-guard verify <page-url> --to <your-domain>
backlink-guard log add <site> --kind directory --anchor "Your Brand"
backlink-guard log
backlink-guard recheck [--to <your-domain>] [--deep] [--free] [--json]
```

From a clone, `python -m backlink_guard` runs the same. Your log, the paid answers (kept 7 days) and the networks seen before are kept in `~/.backlink-guard`, or in `./state` when it is run from a clone that has one; `BACKLINK_GUARD_STATE` moves them.

- **find**: $0.005 a keyword and $0.012 for the search volumes; `--vet` adds the vet cost for the sites found. `--site` leaves your own site out, `--skip` competitors.
- **vet**: about $0.01 a site, plus about $0.16 for the batch (spam scores and search history), the same for one site or thirty: check the sites you are considering in one run; `--topic` adds a column with where each site ranks for your keyword ($0.005 a keyword); `--free` reads the sites only. `--from` reads the sites out of a list (text, Markdown, CSV, JSON or an Excel sheet, as paid backlink lists usually come); `--skip` leaves out your own site, competitors or what you already have (sites or a list file); `--limit` caps a run at 30 sites unless raised. `--deep` adds the site's own backlink profile ($0.024 a site) and looks for its checkout links on inner pages (about $0.05, plus $0.02 a link found); `--recent` asks whether Google is taking in its new pages ($0.008 a site, and slow: GoAnyAPI's search calls take 10 to 120 seconds). Use both before paying for a placement. `--referrals` reads your analytics export (GA4's Traffic acquisition by Session source, as CSV) and adds what each site has sent you. A check that finds one operator's sites missing from the shared spam-link list ends with a link to a filled-in report for it.
- **audit**: about $0.06, with `--deep` (full anchor distribution) about $0.10.
- **verify**: free. Verdicts are `followed link`, `qualified link` (nofollow, sponsored or ugc), `redirect only` (through the site's own /go/ page, also when the target is base64-encoded), `not found`, `unreadable`. Only those three rel values hold back credit; `noopener` and `external` do not. Each link also says where it sits, read from the elements around it: `body text`, `main area`, `header`, `navigation`, `sidebar`, `footer`, `comments` or `author box`. A followed link that is only in a footer, sidebar or navigation is called out: Google lists widely distributed footer, template and widget links among its link spam examples, and an editor's link in the text counts for more.
- **log**: your submissions in `ledger.jsonl`, with a warning past five a week or when one anchor is used over and over.
- **recheck**: the sites in your log (submitted or live) checked again and compared with the last look: a lower verdict, a new finding, and with `--to` a link of yours no longer found. Kept in `recheck.json`. A dozen sites cost a few cents; monthly is enough.

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

In Claude Code, as a plugin:

```bash
claude plugin marketplace add zhuyansen/backlink-guard
claude plugin install backlink-guard@backlink-guard
```

As a skill, for any agent that reads them:

```bash
npx skills add zhuyansen/backlink-guard
```

The skill walks an agent through the same order: vet, the rules, verify, audit. It runs the installed `backlink-guard` command, or `uvx` from this repository, or a clone in `~/backlink-guard`, and says the cost before a paid run.

## Limits

- Signals, not verdicts. A fall in visits next to a spam update is a coincidence in time until someone shows otherwise.
- A site that blocks unknown clients gives no page signals; the report says "blocked".
- Links added by script are not seen by `verify`.
- Private link sellers are invisible to it.
- Visit and rating numbers are third-party estimates.
- The search history is US Google only. A site whose readers are elsewhere can fall in the US and hold at home. A fall shows once two monthly readings agree, so an update that ended last week may not show yet.
- GoAnyAPI is a young service (first released August 2026). Treat it as an enhancement.

## Thanks

- [Loki Yan @loki_yan_seo](https://x.com/loki_yan_seo), whose notes on the 2026 spam updates ("follow the timeline, then go through the spam policies one by one") set the order this tool works in.
- [饭特稀 | Fentix @fantexi997](https://x.com/fantexi997) for [GoAnyAPI](https://goanyapi.com).

MIT.
