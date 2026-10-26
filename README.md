<div align="center">

<img src="https://raw.githubusercontent.com/zhuyansen/backlink-guard/main/docs/logo.svg" width="128" alt="backlink-guard logo: a chain link inside a shield">

# backlink-guard

**Check a link source before you submit to it, the link after it goes live, and your own backlinks for link spam.**

[![PyPI](https://img.shields.io/pypi/v/backlink-guard?color=0ea5e9&label=PyPI)](https://pypi.org/project/backlink-guard/)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://pypi.org/project/backlink-guard/)
[![License: MIT](https://img.shields.io/badge/license-MIT-eab308)](https://github.com/zhuyansen/backlink-guard/blob/main/LICENSE)
[![Stars](https://img.shields.io/github/stars/zhuyansen/backlink-guard?logo=github&color=0f172a)](https://github.com/zhuyansen/backlink-guard/stargazers)
[![Forks](https://img.shields.io/github/forks/zhuyansen/backlink-guard?logo=github&color=0f172a)](https://github.com/zhuyansen/backlink-guard/network/members)
[![Downloads](https://img.shields.io/pepy/dt/backlink-guard?color=22c55e&label=downloads)](https://pepy.tech/projects/backlink-guard)
[![Last commit](https://img.shields.io/github/last-commit/zhuyansen/backlink-guard?color=64748b)](https://github.com/zhuyansen/backlink-guard/commits/main)

[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-io.github.zhuyansen%2Fbacklink--guard-0ea5e9)](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.zhuyansen/backlink-guard)
[![Security-graded by Agent Skills Hub](https://agentskillshub.top/badge/zhuyansen/backlink-guard.svg)](https://agentskillshub.top/skill/zhuyansen/backlink-guard/)
[![skills.sh](https://img.shields.io/badge/skills.sh-zhuyansen%2Fbacklink--guard-0f172a)](https://skills.sh/zhuyansen/backlink-guard)

⭐ **37 of 40 Ahrefs-marked spam sites kept from "submit"**, on 100 sites it had never seen · on PyPI, the official MCP Registry and skills.sh

[Quick start](#quick-start) · [How well it works](#how-well-it-works) · [Where to be](#where-to-be-find) · [Competitors](#links-your-competitors-earned-competitors) · [AI answers](#where-ai-answers-come-from-cited) · [Keys](#keys) · [Agents and MCP](#use-it-from-an-agent-the-skill-and-an-mcp-server) · [中文说明](https://github.com/zhuyansen/backlink-guard/blob/main/README.zh-CN.md)

</div>

Find the pages your searchers already land on, the sites that link to your competitors and not to you, the sites Google's AI Overviews cite for your keywords, and what AI assistants answer when asked for what you make; check a link source **before** you submit your site to it, check the link **after** it goes live, look at your **own** backlink profile for the patterns Google calls link spam, and find the links that point at pages of yours that are gone or redirect badly.

Most backlink tools help you send more. This one tells you where not to send, and when to slow down.

![How backlink-guard works: find the pages your searchers land on, and with competitors, cited and asked the sites your competitors earned and the sites AI answers cite; vet each site (its own pages, GoAnyAPI, Glasser or AIsa), get avoid, caution or ok with the evidence, follow the rules, submit, then verify and log; audit your own profile now and then, with the sites one owner runs; lost lists backlinks landing on 404 pages or redirects, with a suggested 301. What 0.8 to 0.10 added is orange](https://raw.githubusercontent.com/zhuyansen/backlink-guard/main/docs/flow.en.gif)

## Quick start

```bash
pip install backlink-guard
backlink-guard vet mcpservers.org turbo0.com navi.tools producthunt.com clawhomepage.com
```

Python 3.10 or newer, no dependencies; `uvx backlink-guard vet …` runs it without installing. With no key it reads the sites' own pages, for free (`--free` asks for just that). The [keys](#keys) (GoAnyAPI, and Glasser or AIsa) add rating, visits, Google's index and spam scores: about $0.17 for one site and $0.46 for thirty, so check the sites you are considering in one run.

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

## Links your competitors earned: competitors

The sites that already write about your competitors are the ones to tell about what you make. For each competitor, `competitors` lists the referring domains first seen in the last 7 days (the ones already linking to you left out), then the sites that link to two or more of the competitors and not to you, the link intersect. Each comes with a page that links, what kind of page it is and what can honestly be done there.

```bash
backlink-guard competitors yoursite.example --vs competitor-a.example competitor-b.example competitor-c.example
```

> ### competitor-a.example: 941 new referring domains; 1 already link to you, left out
>
> | Site | Rank | First seen | Linking page | Kind |
> |---|---|---|---|---|
> | agenthub.example | 195 | 2026-10-19 | [Skill install and guide](https://agenthub.example/en/p/skill-guide) | article |
> | toolsdir.example | 23 | 2026-10-16 | [Agent Skills Marketplace](https://toolsdir.example/tools/agent-skills-marketplace) | directory |
>
> ## Sites linking to two or more of them, not to you
>
> | Site | Links to | Rank | First seen | Linking page | Kind |
> |---|---|---|---|---|---|
> | compare.example | competitor-a.example, competitor-b.example | 25 | 2026-10-09 | [Best Claude skills marketplaces compared](https://compare.example/compare/claude-skills-marketplaces/) | list |
> | indies.example | competitor-b.example, competitor-c.example | 51 | 2026-05-18 | [Competitor B, made by indies](https://indies.example/products/competitor-b) | directory |

Left out, and named at the end: the sites on the [shared spam-link list](https://github.com/zhuyansen/backlink-spam-list), the links that score 50 or more for spam (every row carries the score), and three or more sites whose linking pages share one title, one network's template, with a filled-in report for the list. On 2026-10-20, 86 of one competitor's 100 newest referring domains were such pages. Rank is what the site's links pass to the competitor, on the backlink index's 0 to 1,000 scale; first seen is when its crawler found the link.

The intersect is one call: the domain intersection in its partial mode returns the domains linking to at least two of the sites given (its page says all of them; tried live, it is two or more). About $0.025 a call, 2N + 2 calls for N competitors: three competitors cost $0.20 on 2026-10-20. `--max-usd` caps a run ($0.30 unless set): a call is made only while its estimate still fits, answers cached in the last 7 days are free, and the report names what the cap left out. Vet a site before you spend time on it; never pay for a followed link.

## Where AI answers come from: cited

An AI Overview cites the pages it was written from. For each keyword, `cited` reads Google's first page with its AI Overview (US, English), says whether the overview cites your site and where you rank, and then counts the sites cited across all your keywords: the places where a mention gets you into the answer.

```bash
backlink-guard cited yoursite.example "claude skills" "agent skills" "claude code skills" "agent skills hub"
```

| Keyword | AI Overview | Sites cited | You | Your position (organic) |
|---|---|---|---|---|
| claude skills | yes | 7 | not cited | not in the top 10 |
| claude code skills | yes | 3 | not cited | not in the top 10 |
| agent skills hub | yes | 7 | ✅ cited: / | not in the top 10 |

| Site | Keywords | Citations | Page cited | Kind |
|---|---|---|---|---|
| github.com | 4 | 6 | [a curated list of Claude skills](https://github.com/) | repo |
| youtube.com | 3 | 8 | [Claude Skills, explained](https://www.youtube.com/) | video |
| skillslist.example | 1 | 1 | [The 68 best Claude skills](https://skillslist.example/en/skills/) | list |

$0.002 a keyword on 2026-10-20, $0.004 when the overview loads after the page; `--max-usd` caps it ($0.10 unless set). A keyword with no AI Overview is said so, which is not the same as not being cited: Google shows an overview when it judges one helpful, and another day, place or searcher can differ.

## What AI assistants answer: questions and asked

People also ask ChatGPT, Perplexity, Claude and Gemini directly, and each of them searches the web before it answers. `questions` writes the questions to ask; `asked` puts them to five assistants and keeps what each one searched for, read and cited.

```bash
backlink-guard questions "a directory of agent skills" --plain > questions.txt
backlink-guard asked yoursite.example --file questions.txt --name "Your Brand" --rank
```

- **questions**: ChatGPT, Claude and Gemini each write the questions they expect to be asked (no web search), merged once: about $0.01.
- **asked**: each question to ChatGPT (its own interface), Google's AI Mode, Perplexity, Claude and Gemini (with their web search). For each assistant, how many answers wrote your domain, gave only your name, cited you, or named a site under your name with another ending (whose mentions are not counted as yours); then the sites and pages cited most, each with its kind and what can honestly be done there, and the searches the assistants ran (AI Mode shows none).
- **--rank**: each of those searches on Google and Bing (US, English, top 20). An assistant reads what its search returns, so a site missing from the results is rarely read at all, and one that ranks without being cited was passed over. The report says where you rank, and puts the sites on the first page of the most searches next to the answers that cited them.

On 2026-10-26, for agentskillshub.top: 8 questions, 56 answers, 67 searches. No answer read or cited the site; it was in Google's top 20 for 3 of the 57 searches Google answered and in Bing's for none of 67. The work is in the search results first.

ChatGPT and Perplexity are asked twice, since their answers vary most: about $0.12 a question with the default samples, $0.0035 a search on each engine for `--rank`. `--max-usd` caps the whole run ($1.00 unless set). Answers asked in the last 7 days come from the cache, so `--rank` after a run costs only the lookups.

## Why

Google's spam updates came in March, June, August and September 2026. "Buying or selling links", "excessive link exchanges", "low-quality directory or bookmark site links" and "using automated programs or services to create links to your site" are all on [Google's list of link spam](https://developers.google.com/search/docs/essentials/spam-policies#link-spam). Directory lists passed around for link building go stale fast and say nothing about any of this.

A verdict here is a set of signals a person can check. It is not Google's judgment: nobody outside Google can tell whether one link is counted, ignored or held against a site. Google ignores most junk links. What the tool is good for is not wasting effort on dead, empty or link-selling sites, and not building the pattern yourself.

## What it checks

| Signal | How | Source | Cost |
|---|---|---|---|
| `find`: the pages that rank for your keywords, by the visitors they get from those searches, and what kind each is | Google's top 30 for each keyword, and its monthly searches | Glasser or AIsa | $0.005 a keyword, plus $0.012 |
| `--topic`: where a site ranks for your keyword, and whether its pages write about it | the same search; the site's pages | Glasser or AIsa, the site | $0.005 a keyword |
| Dead, or a parked or expired domain | reads the home page; one that gives no answer at all is asked again 5 seconds later | the site | free |
| Sells followed links or posts | a price next to "dofollow", "guest post", "link insertion" on the home, submit and pricing pages | the site | free |
| Pages that invite guest or sponsored posts (a note), found even when the home page does not link to them | Google search for its "write for us" and guidelines pages | GoAnyAPI | $0.002 |
| Asks for a link or badge back | the same pages | the site | free |
| Links out to gambling, adult, loan or essay-mill sites | outbound links on the home page | the site | free |
| A URL shortener, or a link network's template page ("<domain> \| Keyword Rankings") | the page title | the site | free |
| Several sites sharing one page template, in this check or an earlier one on this machine | the titles with each site's own name taken out (block pages and platform defaults left out) | the batch, earlier checks | free |
| Several sites reporting to one analytics or ads account (AdSense, Google Analytics, Tag Manager, Clarity, Facebook pixel, Cloudflare Web Analytics), in this check or an earlier one: one operator | the home page | the batch, earlier checks | free |
| First seen | the Wayback Machine's first copy | archive.org | free |
| What Google knows it as (a website, a topic, a company), in the audience table | the suggestions Google Trends gives for the domain and for its name | Google Trends | free |
| A lapsed domain picked up again: archived a year or more before its current registration, registered in the last three years, under 100,000 visits a month | the first copy against the registration date the visits answer carries | archive.org, GoAnyAPI | free with the visits |
| Rating, and a rating with no readers behind it (30 or more, under 5,000 visits a month) | domain rating | GoAnyAPI | $0.002 |
| Reach, and a fall in visits | 12 months of monthly visits; a fall within a month counts once a later month shows it has not come back (in the newest month it is a note), and is shown next to the Google updates that ran around it | GoAnyAPI, Google's status feed | $0.004 |
| Lost its Google search traffic and has not won it back, back to 2022 (a caution within the last year, a note before that) | monthly US Google traffic and ranking keywords; a fall counts when both fall and stay down two months, measured against twelve large sites read in the same call; shown next to the Google updates around it | Glasser or AIsa, Google's status page | $0.12 a batch plus $0.0012 a site |
| Whether Google lists it | `site:` search, only for sites with few visitors; an empty answer is asked twice before it counts, and a search that fails on both sources is asked once more, never read as empty | GoAnyAPI, then AIsa | $0.004 to $0.01 |
| Spam score of the site's own backlinks, counted from 50 | one call for the batch | Glasser or AIsa | $0.025 a batch |
| On the shared list of sites that build or sell spam backlinks, each with public evidence ([backlink-spam-list](https://github.com/zhuyansen/backlink-spam-list)) | the list, read once a run and kept a day; a listed site gets no paid check | GitHub | free |
| Sells links as its business ("PBN", "DR/DA" packages) | the page title | the site | free |
| Thousands of pages, almost none ranking: scaled, low-value content (sites in English) | pages in the site's own sitemaps (read up to 1.5 MB a file, so a floor) against the keywords it ranks for on US Google | the site; Glasser or AIsa | free with the search history |
| `--deep`: a badge network (hundreds of links from each listed site, most in footers, nearly all followed; not read on a site with 100,000 visits a month or more), or an unproven site (under a year old, under 100 linking sites, under 1,000 visits) | backlink summary | Glasser or AIsa | $0.024 a site |
| A checkout link it carries (Stripe, Gumroad, Lemon Squeezy, Polar, Creem, Dodo, Paddle) also sits on dozens of sites built like it: a network selling links through it, or a gambling or adult product injected into hacked sites. Its seller and the sites that merely cite it are not flagged. `--deep` also finds the checkout links on its inner pages, where networks put them | backlinks, plus the other sites' home pages for their titles | Glasser or AIsa | about $0.02 a checkout link; with `--deep` about $0.05 more a site |
| `--recent`: whether Google takes in the pages it keeps adding | `site:` search for the last week and month, each zero asked twice, checked against the site's own sitemap | GoAnyAPI | $0.008 a site |

Glasser or AIsa means whichever key is set, Glasser when both are: they resell the same endpoints at the same prices, but for two searches, `find`'s ($0.006 a keyword through Glasser, $0.005 through AIsa) and `cited`'s (up to $0.006 against $0.004). What Glasser does not sell stays on AIsa: the `site:` search that stands in when GoAnyAPI's fails, `--deep`'s Ahrefs rating and Semrush numbers, and everything `questions` and `asked` ask. See [Keys](#keys).

For your own domain (`audit`): totals and how many referring domains pass ranking credit (GoAnyAPI), new and lost referring domains by week, up to 1,000 of your backlinks one by one with the referring domains behind each anchor, the site-wide links (Glasser or AIsa), the spam score of the sites linking to you, and the referring domains one owner runs (their home pages, free). `lost` reads the same backlinks for the pages of yours they point at that are gone or redirect.

## Your own links: audit and lost

A count of links says little on its own: a site that puts your link in its footer gives you as many links as it has pages. So every count of links comes with the number of referring domains (the registrable domain: `blog.a.example` and `a.example` are one, `alice.github.io` and `bob.github.io` two). One site linking to one page of yours from 20 or more of its pages (`--sitewide` changes it), or from three or more with most of them in its footer, sidebar or navigation, is a site-wide link: one source wherever a share is worked out, and the report says so.

```bash
backlink-guard audit yoursite.example
```

> - Read one by one: 60 of 1,840 links from 21 referring domains (AIsa); 40 links from 1 site, counted once
>
> ℹ️ **Some sites link to you from many of their pages (site-wide): each counts as one source.** 40 links from 40 pages of news.example to /blog/old-launch-notes, 100% in its footer, sidebar or navigation. Each site counted once in the shares here _(Google: Widely distributed links in the footers or templates of various sites)_

| Anchor | Links | Referring domains |
|---|---|---|
| YourSite | 13 | 13 |
| best csv tool | 4 | 4 |

`audit` also reads the home page of each referring domain (free, at most 300, `--homes`; 0 skips it) for the analytics and ads accounts it reports to, as `vet` does: AdSense, Google Analytics, Tag Manager, Clarity, the Facebook pixel, Cloudflare Web Analytics. Three or more sites on one account, two of them linking to you, are one owner's network: its links are one owner's votes (count it as one source), and a network built to link is the pattern Google's spam policies describe. The accounts join the networks seen before, so a site you vet later is matched against them, and when the shared list already holds half of a network, the report links to a filled-in report for the rest. When the backlinks read name fewer sites than `--homes` (one site's strongest 1,000 backlinks came from 29 referring domains), the referring-domains list (Glasser or AIsa) fills up the rest, about $0.035 for 300.

> ⚠️ **Several sites linking to you report to one analytics or ads account: one owner's network, whose links count as one source.** 24 referring domains in 1 network: cloudflare:0a1b2c3d… on poker-casino.example, crime-news.example, mirror.example …, 26 links. Count each network as one source _(Google: Using automated programs or services to create links to your site)_

A media group's titles or a platform's hosted sites can share an account honestly: read the sites before you act. Google ignores most such links; a disavow file is for a manual action.

`lost` asks each page of yours that gets links whether it is still there: one GET each, redirects followed, four at a time, at most 200 pages, the most linked first. Only 404 and 410 make a page dead, also at the end of a redirect chain; any other error is reported apart, as refused or unanswered, never as dead. For each dead page it suggests where to send it: the live page in your own sitemaps (robots.txt or /sitemap.xml, indexes followed, up to 10 files and 50,000 pages) whose path is closest, with the match from 0 to 1, and no suggestion under 0.50.

```bash
backlink-guard lost yoursite.example
```

| Page of yours | Answer | Referring domains | Links | Strongest referring domain | Suggestion | Match |
|---|---|---|---|---|---|---|
| /blog/old-launch-notes | 404 | 8 | 8 | news.example (AIsa rank 520) | 301 to /blog/launch-notes-2026 | 0.77 |
| http://yoursite.example/tools/csv-cleaner | 410 | 3 | 3 | d0.example (AIsa rank 210) | 301 to /tools/csv-cleaner-online | 0.85 |
| /2019/careers | 404 | 1 | 1 | e.example (AIsa rank 90) | no good match (best 0.11) | – |

> ℹ️ **Sites link to pages of yours that no longer exist: the links reach nothing.** 3 pages of yours answer 404 or 410 and have links from 12 referring domains … _(Google: a page that has moved for good takes a permanent server-side redirect, 301 or 308)_

Sorted by referring domains, a site-wide source counted once in Links. Nothing is redirected: it is a list to read, and a page with no good match may be better left a 404 or sent to a parent page you choose. Google's page on [redirects](https://developers.google.com/search/docs/crawling-indexing/301-redirects) is the reference.

The pages of yours that redirect are followed one hop at a time and judged, worst first: **broken** (a loop, more than ten hops, or no page at the end), **soft-lost** (it ends on your home page, on another site, or on a page whose path matches the old one under 0.50; Google's page on [site moves](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes) says redirecting old URLs to one irrelevant page such as the home page "might be treated as a soft 404 error", so the closest live page is suggested as for a dead one), **temporary** (a 302, 303 or 307 on the way: Google keeps showing the old URL), **chain** (two hops or more: Google advises one) or fine.

| Page of yours | Redirect | Referring domains | Links | Verdict | Suggestion | Match |
|---|---|---|---|---|---|---|
| /old-post | 301 → / | 2 | 2 | 🔻 soft-lost: ends on your home page | 301 to /blog/old-post-renamed | 0.62 |
| /tmp | 302 → /tmp-new | 1 | 1 | ⚠️ temporary: 302, a temporary redirect | – | – |
| /zh/weekly/ | 308 → 308 → /zh/go-global/weekly | 1 | 1 | ⚠️ chain: 2 redirects in a row | – | – |

> Redirected well (one permanent hop to a page like it): 1 page(s), e.g. /zh/weekly → /zh/go-global/weekly.

Prices are what the calls cost on 2026-10-13 and 14. Paid answers are cached for 7 days.

A site its own pages already put at avoid (dead, parked, a URL shortener, a network template page, a link seller, links out to gambling sites) gets no paid check: the rest could only add to it. A site that does not load gets one question, its visits, since a site people visit that refuses the check is blocked, not dead. An ok whose check failed where it could have found something (rating, visits, index, backlink profile, checkout links, spam score, search history) is marked incomplete: run it again before relying on it.

## Commands

```bash
backlink-guard find "<keyword>" [more ...] [--site yoursite.com] [--skip competitors.txt] [--vet] [--json]
backlink-guard vet <site> [more ...] [--from list.xlsx] [--skip yoursite.com] [--limit 30] [--topic "keyword"] [--referrals ga4.csv] [--deep] [--recent] [--free] [--fresh] [--json]
backlink-guard competitors <your-domain> --vs <competitor> [more ...] [--days 7] [--limit 100] [--max-usd 0.30] [--json]
backlink-guard cited <your-domain> "<keyword>" [more ...] [--max-usd 0.10] [--json]
backlink-guard questions "<what you make>" [--count 10] [--plain] [--json]
backlink-guard asked <your-domain> ["<question>" ...] [--file questions.txt] [--name "Your Brand"] [--engines chatgpt,ai_mode,perplexity,claude,gemini] [--samples N] [--rank] [--max-usd 1.00] [--json]
backlink-guard audit <your-domain> [--deep] [--sitewide 20] [--rows 1000] [--homes 300] [--json]
backlink-guard lost <your-domain> [--sitewide 20] [--rows 1000] [--json]
backlink-guard verify <page-url> --to <your-domain>
backlink-guard log add <site> --kind directory --anchor "Your Brand"
backlink-guard log
backlink-guard recheck [--to <your-domain>] [--deep] [--free] [--json]
```

From a clone, `python -m backlink_guard` runs the same. Your log, the paid answers (kept 7 days) and the networks seen before are kept in `~/.backlink-guard`, or in `./state` when it is run from a clone that has one; `BACKLINK_GUARD_STATE` moves them.

- **find**: $0.005 a keyword and $0.012 for the search volumes; `--vet` adds the vet cost for the sites found. `--site` leaves your own site out, `--skip` competitors.
- **vet**: about $0.01 a site, plus about $0.16 for the batch (spam scores and search history), the same for one site or thirty: check the sites you are considering in one run; `--topic` adds a column with where each site ranks for your keyword ($0.005 a keyword); `--free` reads the sites only. `--from` reads the sites out of a list (text, Markdown, CSV, JSON or an Excel sheet, as paid backlink lists usually come); `--skip` leaves out your own site, competitors or what you already have (sites or a list file); `--limit` caps a run at 30 sites unless raised. `--deep` adds about $0.19 a site: the site's own backlink profile ($0.024), its technology ($0.012), how often ChatGPT's answers mention it ($0.10) and its checkout links on inner pages (about $0.05, plus $0.02 a link found); with an AIsa key also Ahrefs' rating ($0.08) and Semrush's numbers ($0.001); `--recent` asks whether Google is taking in its new pages ($0.008 a site, and slow: GoAnyAPI's search calls take 10 to 120 seconds). Use both before paying for a placement. `--referrals` reads your analytics export (GA4's Traffic acquisition by Session source, as CSV) and adds what each site has sent you. A check that finds one operator's sites missing from the shared spam-link list ends with a link to a filled-in report for it.
- **competitors**: about $0.025 a call, 2N + 2 calls for N competitors (three: about $0.20). `--days` sets what new means (7), `--limit` the referring domains read from each list (100, at most 1,000), `--max-usd` the most a run may spend ($0.30); cached answers are free and what the cap left out is named.
- **cited**: $0.002 a keyword through AIsa, $0.004 when the overview loads late; through Glasser $0.004 and $0.006; `--max-usd` caps it ($0.10).
- **questions**: about $0.01 for the three writers; `--count` sets how many each writes (10), `--plain` prints the list for a file.
- **asked**: ChatGPT and AI Mode $0.004 an answer, Perplexity about $0.006, Claude and Gemini about $0.045 (2026-10-21): about $0.12 a question, with ChatGPT and Perplexity asked twice. `--samples` asks every assistant that many times, `--engines` picks them, `--name` adds a name the answers may call you by. `--rank` adds $0.0035 a search on Google and on Bing (2026-10-26). `--max-usd` caps the run ($1.00): the most-run searches are looked up first, and the report names what the cap left out.
- **audit**: about $0.12, with `--deep` (full anchor distribution) about $0.16. Of that, about $0.06 is the 1,000 backlinks read one by one (`--rows` asks for fewer: 100 cost $0.028 on 2026-10-18). Without a Glasser or AIsa key the 20 top linking pages from GoAnyAPI stand in. The home pages of up to 300 referring domains are read for shared accounts (free; `--homes` changes it, 0 skips it), with about $0.035 more when the backlinks read name fewer sites than that.
- **lost**: the same backlinks, so nothing more after an `audit` of the same site in the last 7 days, else about $0.06; asking your pages (and following their redirects hop by hop) and reading your sitemaps is free.
- **verify**: free. Verdicts are `followed link`, `qualified link` (nofollow, sponsored or ugc), `redirect only` (through the site's own /go/ page, also when the target is base64-encoded), `not found`, `unreadable`. Only those three rel values hold back credit; `noopener` and `external` do not. Each link also says where it sits, read from the elements around it: `body text`, `main area`, `header`, `navigation`, `sidebar`, `footer`, `comments` or `author box`. A followed link that is only in a footer, sidebar or navigation is called out: Google lists widely distributed footer, template and widget links among its link spam examples, and an editor's link in the text counts for more.
- **log**: your submissions in `ledger.jsonl`, with a warning past five a week or when one anchor is used over and over.
- **recheck**: the sites in your log (submitted or live) checked again and compared with the last look: a lower verdict, a new finding, and with `--to` a link of yours no longer found. Kept in `recheck.json`. A dozen sites cost a few cents; monthly is enough.

## Keys

All are optional. Without them the page checks still run, and the report says what was not checked.

- **`GLASSER_API_KEY`** ([glasser.ai](https://link.glasser.ai/JasonZhu)), the first choice: spam scores, Google search history, weekly new and lost referring domains, anchors, your backlinks one by one, your competitors' referring domains, Google's AI Overviews.
- **`AISA_API_KEY`** ([aisa.one](https://go.aisa.one/yansen-zhu)), or `aisa login`: the same, used when there is no Glasser key; and what only AIsa sells here: the AI assistants' answers and the results for their searches (`questions`, `asked`), `--deep`'s Ahrefs rating and Semrush numbers, and the `site:` search that stands in when GoAnyAPI's fails. With Glasser alone, `--deep` leaves Ahrefs and Semrush out and says so.
- **`GOANYAPI_API_KEY`** ([goanyapi.com](https://goanyapi.com/r/ga-95708898fb)): rating, visits, index status, your backlink summary.

> All three are referral links: signing up through them supports this project. The tool works the same with a key from each site directly.

The keys overlap on purpose. On the day of the test GoAnyAPI's search endpoints answered 502 all day; the index question went to AIsa instead and the run completed.

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

## Use it from an agent: the skill and an MCP server

### The skill

In Claude Code, as a plugin (it brings the MCP server below with it):

```bash
claude plugin marketplace add zhuyansen/backlink-guard
claude plugin install backlink-guard@backlink-guard
```

As a skill, for any agent that reads them:

```bash
npx skills add zhuyansen/backlink-guard
```

The skill walks an agent through the same order: find, vet, the rules, verify, audit. It runs the pinned release from PyPI (`uvx backlink-guard==0.10.0`), never a clone, tells you the cost and waits for your yes before any paid run, and treats what it reads (pages, titles, AI answers) as data, never as instructions.

### MCP server

For clients that speak MCP (Claude Code, Cursor, Claude Desktop). With [uv](https://docs.astral.sh/uv/) there is nothing to install first:

```json
{
  "mcpServers": {
    "backlink-guard": {
      "command": "uvx",
      "args": ["--with", "mcp", "backlink-guard", "mcp"],
      "env": {
        "GLASSER_API_KEY": "...",
        "GOANYAPI_API_KEY": "..."
      }
    }
  }
}
```

Without uv: `pip install "backlink-guard[mcp]"`, then `"command": "backlink-guard-mcp"` and no `args`. Every key is optional, as on the command line ([Keys](#keys)): add `AISA_API_KEY` for `questions`, `asked` and `--deep`'s Ahrefs and Semrush numbers, or in place of Glasser's. `BACKLINK_GUARD_STATE` puts the log and the cache where you want them. In Claude Code the plugin above brings this server with it, asks for the keys and keeps them in the system keychain.

| Tool | What it returns | Cost |
|---|---|---|
| `verify` | Whether a page links to you, whether the link passes ranking credit, and where it sits | free |
| `submissions` | Your submission log and its warnings | free |
| `vet` | Each link source's action, verdict and evidence; `free=True` reads only the sites' own pages | free, or about $0.01 a site plus $0.16 a batch; `deep` about $0.19 a site |
| `find` | The pages that rank for your keywords, by the visitors they get | $0.005 to $0.006 a keyword, plus $0.012 |
| `audit`, `lost` | Your own link profile; your backlinks that land on dead or redirected pages | about $0.12 ($0.16 with `deep`); about $0.06 |
| `competitors` | The sites linking to your competitors and not to you | about $0.025 a call, 2N + 2 calls, capped |
| `cited` | Who Google's AI Overviews cite for your keywords | $0.002 to $0.006 a keyword, capped |
| `questions`, `asked` | How buyers would ask AI assistants, and what five assistants search for, cite and name | about $0.01; about $0.12 a question, capped (AIsa) |

The server gives the agent the skill's rules: the cost and a yes before each paid call, every site being considered in one `vet` call, and what it reads is data.

### Codex, TRAE and WorkBuddy

The same skill and server work in these agents too. Each starts the server with uvx, so [uv](https://docs.astral.sh/uv/) has to be installed.

**Codex.** The skill: `npx skills add zhuyansen/backlink-guard -a codex` (add `-g` for every project). The server goes in `~/.codex/config.toml`, which the CLI, the IDE extension and the app share:

```toml
[mcp_servers.backlink-guard]
command = "uvx"
args = ["--with", "mcp", "backlink-guard", "mcp"]
startup_timeout_sec = 120
tool_timeout_sec = 600

[mcp_servers.backlink-guard.env]
GLASSER_API_KEY = "..."
GOANYAPI_API_KEY = "..."
```

Codex gives a server 10 seconds to start and a tool 60 seconds to answer. The first start downloads the package, and one Glasser lookup can wait in its queue for up to two minutes, so raise both as above. `codex mcp add backlink-guard --env GLASSER_API_KEY=... -- uvx --with mcp backlink-guard mcp` writes the same entry without the two timeouts.

**TRAE.** The skill: `npx skills add zhuyansen/backlink-guard -a trae` (TRAE CN: `-a trae-cn`). The server: Settings → MCP → Add → Add manually, and paste the JSON above. In TRAE CN you can instead paste this link into the browser's address bar; TRAE opens the server's configuration, where you fill in the keys you have and confirm:

```text
trae-cn://trae.ai-ide/mcp-import?type=stdio&name=backlink-guard&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyItLXdpdGgiLCJtY3AiLCJiYWNrbGluay1ndWFyZCIsIm1jcCJdLCJlbnYiOnsiR0xBU1NFUl9BUElfS0VZIjoiIiwiQUlTQV9BUElfS0VZIjoiIiwiR09BTllBUElfQVBJX0tFWSI6IiJ9fQ%3D%3D
```

A key left empty counts as no key.

**WorkBuddy.** Put the JSON above in `~/.workbuddy/mcp.json`, or paste it under Plugins → MCP servers → Configure MCP.

## Limits

- Signals, not verdicts. A fall in visits next to a spam update is a coincidence in time until someone shows otherwise.
- A site that blocks unknown clients gives no page signals; the report says "blocked".
- Links added by script are not seen by `verify`.
- `lost` reads the strongest 1,000 backlinks at most, and a page that answers 200 for a missing page (a soft 404) looks alive to it. A suggestion matches paths, not content: read the page before you redirect to it. The same goes for a soft-lost redirect: a renamed page whose path shares little with the old one is called soft-lost until you read it.
- `competitors` sees what the backlink index's crawler has found: first seen is when it found a link, which can be later than the link. A linking page is looked up under a site's main domain and its www. form, so a site that links only from another subdomain shows none. A network page with a title of its own and a spam score under 50 stays in the list: vet a site before you spend time on it.
- `cited` reads Google's US English results once: an AI Overview changes with the day, the place and the searcher.
- `asked` reaches the assistants through their APIs (ChatGPT through its own interface): US English, no history and no memory, not what a signed-in person sees. An answer differs from one ask to the next, so count what recurs. Gemini cites through Google's redirect, so only its sites are known, not its pages.
- `--rank` reads Google's and Bing's US English results once. They stand in for the indexes the assistants search, each of which has its own. On 2026-10-26 AIsa's Google results answered "Internal SE Server Error." to 21 of 67 searches: each failed search is asked once more, and one that fails twice is counted as failed, never as a search you are missing from.
- Shared accounts are read from a home page as served: an ID a tag manager or a script adds later is not seen, and a link network with no analytics at all shares nothing to read.
- Private link sellers are invisible to it.
- Visit and rating numbers are third-party estimates.
- The search history is US Google only. A site whose readers are elsewhere can fall in the US and hold at home. A fall shows once two monthly readings agree, so an update that ended last week may not show yet.
- GoAnyAPI is a young service (first released August 2026). Treat it as an enhancement.

## Thanks

- [Loki Yan @loki_yan_seo](https://x.com/loki_yan_seo), whose notes on the 2026 spam updates ("follow the timeline, then go through the spam policies one by one") set the order this tool works in.
- [饭特稀 | Fentix @fantexi997](https://x.com/fantexi997) for [GoAnyAPI](https://goanyapi.com).

MIT.

<!-- mcp-name: io.github.zhuyansen/backlink-guard -->
