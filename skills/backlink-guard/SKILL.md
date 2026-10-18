---
name: backlink-guard
description: Check a link source before submitting a site to it, verify a listing after it goes live, and audit a site's own backlink profile for patterns that read as link spam. Use when the user wants to submit a site, tool or repository to directories, awesome lists or guest-post sites, asks whether a directory or link source is safe or worth it, wants to check whether a backlink is followed, or asks for a backlink audit or spam check after a Google spam update. Runs the backlink-guard command line; a GOANYAPI_API_KEY and an AISA_API_KEY add the paid signals.
---

# Backlink guard

Four jobs, in the order a careful person does them: find the pages your searchers already land on, check a place before you submit, check the link after it is live, and look at your own profile now and then. The tool gives signals with their evidence. It does not submit anything, and it is not Google's verdict.

## Before you run anything

1. Find the tool, in this order: the `backlink-guard` command (installed with `pip install backlink-guard`); `uvx backlink-guard` when `uv` is there; else clone https://github.com/zhuyansen/backlink-guard to `$BACKLINK_GUARD_DIR` or `~/backlink-guard` and run `python -m backlink_guard` from that folder. The commands below are written as `backlink-guard`; use the form that works. Python 3.10 or newer, no dependencies. The log, the paid answers and the networks seen before are kept in `~/.backlink-guard` (or `./state` in a clone that has one).
2. Keys are optional, and each adds signals:
   - `GOANYAPI_API_KEY` (https://goanyapi.com/r/ga-95708898fb): a site's rating, a year of monthly visits, whether Google still lists it, and the summary of your own backlinks.
   - `AISA_API_KEY` (https://go.aisa.one/yansen-zhu): spam scores, new and lost referring domains by week, anchors.
   Without a key the page checks still run. Say which signals are missing: a site can pass the page checks and have no audience at all.
3. Say the cost before a paid run. `find`: about 0.005 USD a keyword plus 0.012 USD for the search volumes, `--vet` then adds the vet cost. `vet`: about 0.01 USD a site plus about 0.16 USD for the batch (spam scores and search history), the same for one site or thirty, so put every site the user is considering in one call (one site about 0.17 USD in all, thirty about 0.46 USD); `--deep` adds 0.024 USD a site, `--recent` 0.008 USD a site (and minutes). Before the user pays for any placement, run both. `audit`: about 0.12 USD, with `--deep` about 0.16 USD. `lost`: about 0.06 USD, nothing more after an `audit` of the same site in the last 7 days. `verify` and `log` are free. Answers are cached for 7 days, so asking again costs nothing.

## 1. Where to be: find

```bash
backlink-guard find "claude skills" "claude code skills" --site yoursite.com --json
```

Start here when the user asks where to get links or listings. It reads Google's top 30 for each keyword and keeps the pages that are not the user's: directories, lists, articles, videos, threads, repositories. Each page has `kind`, `ranks` (keyword and position), `visitors` (monthly searches times the usual click share of that position: a size, not a count) and `action`. The pages are sorted by `visitors`: a page that ranks for the user's keyword sends people already looking for what they make, which is the point of a link.

- `list`: ask to be added (a pull request to a GitHub list, a short note to an article's author).
- `directory`: submit, after vet. A GitHub topic page means adding that topic to the repository.
- `article`, `video`: an author or creator who covered the topic. Offer what the page lacks; a paid mention is marked as such.
- `community`: answer where it genuinely helps. Never drop links in bulk.
- `docs`, `site`: official pages and products; not sources.

`--vet` vets the directories and the article sites found (not platforms like GitHub, Medium or YouTube, where the page and its author matter, not the platform's numbers). Use `--skip` for competitors.

## 2. Before submitting: vet

```bash
backlink-guard vet mcpservers.org turbo0.com navi.tools --json
```

One call for all the sites the user is considering. Add `--topic "their keyword"` to see where each site ranks for it (`fit`): a site that ranks for the user's keyword is relevant by construction; `mentions` says its pages at least write about it. When they come as a list (a competitor gap export, a paid backlink list, a note), pass the file: `--from list.xlsx --skip yoursite.com --skip competitors.txt`. A run checks 30 sites unless `--limit` is raised; say the cost of a bigger run first. Each row has `action` (`skip`, `look first`, `free only`, `low value`, `submit`) with `action_reason`, `grade` (`ok`, `caution`, `avoid`: one avoid finding makes avoid, caution takes two caution findings), `risk` (3 for each avoid finding, 1 for each caution: use it to order sites with the same grade, not as a probability), `reach` (`high`, `medium`, `low`), `metrics` and `flags`; every flag has `meaning`, `evidence` and, where one applies, the line of Google's link spam policy it stands next to.

How to act on it:

- Lead with `action`, and say `action_reason` in a sentence. `skip`: do not submit. `look first`: a check failed or the site refused it, it may be one of an operator's several sites, or two findings stand against it; read the evidence aloud and let the user decide. `free only`: a free listing is fine, but never pay for a followed link, never link back as a condition, never show its badge. `low value`: nothing against it, but under 1,000 visits a month; only if it costs nothing and fits. `submit`: none of these.
- `networks` in the result: one operator's sites that the shared spam-link list lacks, most of them flagged, each with `report`, a link to a filled-in report form for the list. Offer the link; opening it sends nothing, and only the user decides to submit it.
- A `listed` finding: the site is on the shared list of spam-link sources (github.com/zhuyansen/backlink-spam-list), with the entry's evidence. If the user finds a network the list lacks, suggest reporting it there, with evidence anyone can check.
- `avoid` (dead, parked, not listed by Google, a URL shortener, a link network's template page, a link seller, or linking out to gambling and similar sites): do not submit. Lists of "the backlink sources other sites use" are full of these: they are there because people submit to them in bulk.
- `caution`: read the evidence aloud to the user and let them decide.
- Each row also has `policy` (`avoid`, `caution`, `clean`: what a link there would mean under Google's link spam policies, one finding being enough) and `value` (`high`, `medium`, `low`, or `none` when nobody can reach the site). Give the user both, apart: a high-value site with a policy caution (`paid_follow`) is worth a free listing and never a payment; a site with value `none` is not worth the time, whatever else it says.
- `ok` with one finding under Why: one caution alone is not a verdict. Name it in a sentence; for `paid_follow` the free listing is fine, but never pay for a followed link.
  - **Sells followed links** (`paid_follow`): the free listing may still be fine. Never pay for a followed link: a paid link must carry `rel="sponsored"` or `nofollow`.
  - **Asks for a link or badge back** (`link_exchange`): one is a choice; a habit of it is a link exchange.
  - **Visits fell sharply in a month** (`traffic_cliff`): the evidence names the Google updates that ran around then. That is context, not proof of a penalty. Say it that way. A fall in the newest month of the data is only a note (`traffic_drop`) until the next month confirms it: in September 2026 one visits estimate halved for many sites whose Google traffic held. Say "check again next month", not "it was hit".
  - **Lost its Google search traffic** (`search_fall`, the last 12 months; `old_search_fall` is the same before that, a note): US Google traffic and ranking keywords fell together and have not come back, with the updates around then. Strong reason not to pay for a placement: Google already rates the site lower. Still context, not proof of a penalty, and US only: a site read mostly elsewhere can fall in the US and hold at home. When `traffic_cliff` fires on the same site, the two sources agree.
  - **Thousands of pages, almost none ranking** (`scaled_pages`): the site's own sitemaps list 1,000 or more pages for every keyword it ranks for on US Google. The shape of scaled, low-value content; on the test set most such sites were marked spam by Ahrefs. Not checked for sites in another language.
  - **High rating, almost no visitors** (`hollow_rating`): the rating was built with links. A listing there reaches nobody.
  - **High spam score** (`spam_score`): the site's own backlinks look manufactured.
  - **One template across several sites** (`same_template`): one operator's network, found in this check or against sites from earlier checks on this machine. Treat them as one site at most.
  - **One analytics or ads account across several sites** (`same_owner`): the same AdSense, Analytics, Tag Manager, Clarity or Facebook pixel account, in this check or an earlier one. One operator; treat them as one site at most.
  - **Badge network** (`badge_network`, with `--deep`): its rating comes from the badges every listed site must show. A listing there is a link exchange; never pay for it.
  - **Unproven** (`unproven`, with `--deep`): new, almost nobody links to it, almost nobody visits. Ahrefs marks most such sites spam. Free to submit if it costs nothing; never pay.
  - **Not indexing** (`not_indexing`, with `--recent`): it keeps adding pages and Google shows none from the last 30 days. Say that `site:` counts are incomplete, and suggest checking again in a week before paying. `inactive` only means no new pages; it is not a fault. A failed search is reported as failed, never as zero.
- `ok` with `reach: low`: harmless and useless. Skip it unless it costs nothing.
- A `blocked` note means the site refused the check: the page signals are missing, not clean.
- `incomplete`: it looked ok, but a check that could have found something failed (`missing` says which). Run it again before calling it ok.
- A row with `skipped`: its own pages already put it at avoid, so no paid check was bought for it.

What the check cannot see: a site that sells links privately and says nothing on its pages. In the test set, one of five media sites that publish contributed posts stated a fee; for the other four nothing could be read.

## 3. The rules for submitting

These are the rules Agent Skills Hub worked to. Follow them whatever the tool says.

- Submit only the user's own project, and only where it fits the list's subject and format. A list that does not fit is skipped, not argued with.
- Read the list's contribution rules first. Where they ask for a human (some lists forbid agents and the `gh` command line), prepare the text and hand it to the user.
- One pull request or submission per list. Never resubmit to push a queue.
- A handful a week, not a batch. Record each one, then check the pace:

```bash
backlink-guard log add mcpservers.org --kind directory --anchor "Agent Skills Hub" --url https://mcpservers.org/submit
backlink-guard log
```

- Vary the anchor: the brand name, the bare URL, a plain description. The log flags one anchor used over and over.
- Do not use tools that create links in bulk. Google lists "using automated programs or services to create links to your site" as link spam, and a hundred directory links in a week is the pattern.

## 4. After it is listed: verify

```bash
backlink-guard verify https://mcpservers.org/servers/you/your-tool --to yoursite.com
backlink-guard log set mcpservers.org --status live --url https://mcpservers.org/servers/you/your-tool
```

Verdicts: `followed link` (passes ranking credit), `qualified link` (nofollow, sponsored or ugc: visitors only), `redirect only` (goes through the site's own redirect page: visitors only), `not found`, `unreadable`. Only those three rel values hold back credit; `noopener` and `external` do not. Each link also has a `placement`: `body text`, `main area`, `header`, `navigation`, `sidebar`, `footer`, `comments` or `author box`. Say where it is: a link an editor put in the body text is worth more than one in a footer or sidebar, and a followed link that appears only in a footer or widget across many pages is the template-link pattern Google lists as link spam. A link a script adds after load is not seen: the result says so, and a browser check settles it. If the user paid for a placement, compare what was promised with what is there.

## 5. Now and then: audit your own profile

```bash
backlink-guard audit yoursite.com --deep --json
```

It reports the totals, how many referring domains pass credit, new and lost referring domains by week, the anchors with the referring domains behind each, the site-wide links, and which of the top linking sites score high for spam. Every count of links comes with its count of referring domains: say both, and lead with domains. Flags:

- `velocity_spike`: a week far above the usual. Ask what was done that week.
- `anchor_repeat`: one keyword anchor on a large share of links.
- `spam_anchor`: anchors that sell links or name gambling and similar trades. Someone else's network usually puts them there. Report it; do not alarm.
- `spammy_referrers`: several of the top linking sites score high for spam. If the user paid any of them, that is the lesson for next time.
- `sitewide` (a note): one site links to one page of the user's from many of its pages (20 or more by default, `--sitewide` changes it), or from a few with most of them in its footer, sidebar or navigation. It is counted as one source in the anchor shares, and the output says so ("N links from 1 site, counted once"). Say it that way: a partner's footer link is common; it is the pattern Google describes only when it is placed for ranking.

## 5b. Links to pages that are gone: lost

```bash
backlink-guard lost yoursite.com --json
```

From the same backlinks, it asks each page of the user's that gets links whether it is still there (free, four at a time) and lists the ones that answer 404 or 410, most referring domains first, each with the strongest referring domain and a `suggest`: the live page in the user's own sitemaps whose path is closest, with its `score` from 0 to 1, or no good match under 0.50. Any other error is `blocked` and no answer is `unreachable`: neither is dead, so do not call them lost. Present the list as suggestions for permanent (301 or 308) redirects, the user's call page by page; the tool redirects nothing, and a suggestion with a low score or a different subject is better left as a 404 or pointed at a parent page the user picks.

Google ignores most junk links rather than punishing them. Do not recommend a disavow file unless the user has a manual action for links in Search Console.

## 6. Monthly: the sites you are already on

```bash
backlink-guard recheck --to yoursite.com --json
```

It checks the sites in the log (submitted or live) again and compares them with the last look: a lower verdict, a new finding against a site, and with `--to` a link of the user's no longer found. Report only what got worse, with its evidence. A site that turned avoid (parked, dropped by Google, carrying an injected checkout link) is one to stop sending people to; Google ignores most bad links, so asking for removal is rarely needed. It only works if the log is kept: `log add` after every submission.

If the user has analytics, ask for the referral export (GA4: Reports, Acquisition, Traffic acquisition, by Session source, exported as CSV) and pass it to vet with `--referrals`. `sent_you` is what each site really sent: on one young site, 10 of the 14 sites rated high reach had sent visits in 30 days, 2 of the 37 rated low.

## Deliver

- For `find`: the keywords with their searches, then the pages worth being on, busiest first (page, kind, where it ranks, visitors, what to do), then the five or so the user should act on this week and how. Say plainly that visitors are an estimate of size.
- For `vet`: a table (site, action, verdict, reach, rating, visits a month, spam score, fit when `--topic` was given, why), then each flagged site's evidence, then what was not checked and why (missing key, failed source, blocked site), then a short recommendation: where to submit first, what to skip, and the report links of any `networks`.
- For `audit`: the numbers, the findings with evidence, and at most three things to do.
- For `lost`: the dead pages with their referring domains and the suggested 301 targets, the ones with no good match apart, then what was blocked or unreachable.
- Never add a site, a number or a verdict from your own knowledge. The output is what the tool saw today.
