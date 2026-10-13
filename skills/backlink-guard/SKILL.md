---
name: backlink-guard
description: Check a link source before submitting a site to it, verify a listing after it goes live, and audit a site's own backlink profile for patterns that read as link spam. Use when the user wants to submit a site, tool or repository to directories, awesome lists or guest-post sites, asks whether a directory or link source is safe or worth it, wants to check whether a backlink is followed, or asks for a backlink audit or spam check after a Google spam update. Runs the backlink-guard command line; a GOANYAPI_API_KEY and an AISA_API_KEY add the paid signals.
---

# Backlink guard

Three jobs, in the order a careful person does them: check the place before you submit, check the link after it is live, and look at your own profile now and then. The tool gives signals with their evidence. It does not submit anything, and it is not Google's verdict.

## Before you run anything

1. Find the tool: `$BACKLINK_GUARD_DIR` if set, else `~/backlink-guard`; clone https://github.com/zhuyansen/backlink-guard there if missing. Run every command from that directory. Python 3.10 or newer; nothing to install.
2. Keys are optional, and each adds signals:
   - `GOANYAPI_API_KEY` (https://goanyapi.com/r/ga-95708898fb): a site's rating, a year of monthly visits, whether Google still lists it, and the summary of your own backlinks.
   - `AISA_API_KEY` (https://go.aisa.one/yansen-zhu): spam scores, new and lost referring domains by week, anchors.
   Without a key the page checks still run. Say which signals are missing: a site can pass the page checks and have no audience at all.
3. Say the cost before a paid run. `vet`: about 0.01 USD a site plus 0.025 USD for the batch. `audit`: about 0.06 USD, with `--deep` about 0.10 USD. `verify` and `log` are free. Answers are cached for 7 days, so asking again costs nothing.

## 1. Before submitting: vet

```bash
python -m backlink_guard vet mcpservers.org turbo0.com navi.tools --json
```

One call for all the sites the user is considering. Each row has `grade` (`ok`, `caution`, `avoid`), `reach` (`high`, `medium`, `low`), `metrics` and `flags`; every flag has `meaning`, `evidence` and, where one applies, the line of Google's link spam policy it stands next to.

How to act on it:

- `avoid` (dead, parked, not listed by Google, or linking out to gambling and similar sites): do not submit.
- `caution`: read the evidence aloud to the user and let them decide.
  - **Sells followed links** (`paid_follow`): the free listing may still be fine. Never pay for a followed link: a paid link must carry `rel="sponsored"` or `nofollow`.
  - **Asks for a link or badge back** (`link_exchange`): one is a choice; a habit of it is a link exchange.
  - **Visits fell sharply in a month** (`traffic_cliff`): the evidence names the Google updates that ran around then. That is context, not proof of a penalty. Say it that way.
  - **High rating, almost no visitors** (`hollow_rating`): the rating was built with links. A listing there reaches nobody.
  - **High spam score** (`spam_score`): the site's own backlinks look manufactured.
- `ok` with `reach: low`: harmless and useless. Skip it unless it costs nothing.
- A `blocked` note means the site refused the check: the page signals are missing, not clean.

What the check cannot see: a site that sells links privately and says nothing on its pages. In the test set, one of five media sites that publish contributed posts stated a fee; for the other four nothing could be read.

## 2. The rules for submitting

These are the rules Agent Skills Hub worked to. Follow them whatever the tool says.

- Submit only the user's own project, and only where it fits the list's subject and format. A list that does not fit is skipped, not argued with.
- Read the list's contribution rules first. Where they ask for a human (some lists forbid agents and the `gh` command line), prepare the text and hand it to the user.
- One pull request or submission per list. Never resubmit to push a queue.
- A handful a week, not a batch. Record each one, then check the pace:

```bash
python -m backlink_guard log add mcpservers.org --kind directory --anchor "Agent Skills Hub" --url https://mcpservers.org/submit
python -m backlink_guard log
```

- Vary the anchor: the brand name, the bare URL, a plain description. The log flags one anchor used over and over.
- Do not use tools that create links in bulk. Google lists "using automated programs or services to create links to your site" as link spam, and a hundred directory links in a week is the pattern.

## 3. After it is listed: verify

```bash
python -m backlink_guard verify https://mcpservers.org/servers/you/your-tool --to yoursite.com
python -m backlink_guard log set mcpservers.org --status live --url https://mcpservers.org/servers/you/your-tool
```

Verdicts: `followed link` (passes ranking credit), `qualified link` (nofollow, sponsored or ugc: visitors only), `redirect only` (goes through the site's own redirect page: visitors only), `not found`, `unreadable`. Only those three rel values hold back credit; `noopener` and `external` do not. A link a script adds after load is not seen: the result says so, and a browser check settles it. If the user paid for a placement, compare what was promised with what is there.

## 4. Now and then: audit your own profile

```bash
python -m backlink_guard audit yoursite.com --deep --json
```

It reports the totals, how many referring domains pass credit, new and lost referring domains by week, the anchors, and which of the top linking sites score high for spam. Flags:

- `velocity_spike`: a week far above the usual. Ask what was done that week.
- `anchor_repeat`: one keyword anchor on a large share of links.
- `spam_anchor`: anchors that sell links or name gambling and similar trades. Someone else's network usually puts them there. Report it; do not alarm.
- `spammy_referrers`: several of the top linking sites score high for spam. If the user paid any of them, that is the lesson for next time.

Google ignores most junk links rather than punishing them. Do not recommend a disavow file unless the user has a manual action for links in Search Console.

## Deliver

- For `vet`: a table (site, verdict, reach, rating, visits a month, spam score, why), then each flagged site's evidence, then what was not checked and why (missing key, failed source, blocked site), then a short recommendation: where to submit first, what to skip.
- For `audit`: the numbers, the findings with evidence, and at most three things to do.
- Never add a site, a number or a verdict from your own knowledge. The output is what the tool saw today.
