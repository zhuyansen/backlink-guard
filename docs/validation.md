# How backlink-guard was tested

[中文](validation.zh-CN.md) · [README](../README.md)

Every rule in the tool came out of one of these tests, run on real sites with their evidence kept. The README has the summary; this is the record, in the order the tests were run.

## Tried on 31 sites (2026-10-13)

Both keys set; the whole run cost about $0.30. The raw rows with their evidence are in [validation-2026-10-13.json](validation-2026-10-13.json).
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
- **Ten sites lost 46% to 80% of their visits within one month**, in August or September 2026 (the check looks at the last three months), the months of two spam updates. None of the ten well-known sites did: their September was between 74% and 181% of their August. Two cautions. It is a coincidence in time, shown as such. And seven of the ten falls are in the newest month of the data, which estimates like these sometimes revise. (Since 0.5 a fall in the newest month is a note until the next month confirms it: see the sixth test.)
- **One rating meant nothing**: 81, with about 2,200 visits a month.
- **A second test, on a paid list (2026-10-14)**: the top of a list of "backlink sources most cited by AI sites". Of its first fourteen, nine were URL shorteners or one network's "Keyword Rankings" template pages: rating 36 to 49, under 2,500 visits a month, several no longer listed by Google. The first version called most of them ok. The shortener, network and shared-template checks and the hollow-rating threshold lowered from 60 to 30 now mark all nine avoid; the 31 sites above came out the same.
- **A third test, against Ahrefs' own SPAM mark (2026-10-14)**: 90 sites linking to one young site, 33 of them marked SPAM in Ahrefs. External data reproduces the mark up to a cross-validated AUC of about 0.75, almost all of it from how new the site is, how few sites link to it and how few people visit; more features did not raise it. So the tool does not try to copy the mark. It names the two mechanisms behind most of it: `unproven` (23 hits, 17 marked; the other 6 look no better) and `badge_network` (7 hits, 4 marked; the other 3 have the same footer-badge profile). Together they catch 21 of the 33.
- **A fourth test, Google's own record (2026-10-14)**: had Google already cut these sites down? Monthly estimates of US Google traffic and ranking keywords since 2022, for the 90 sites and the 31 above. Two things in that data look like a fall and are not one. The database itself moves: in December 2021 seven in ten sites "fell" more than 60% in one month and the twelve large control sites lost a third, and in November 2024 the median fell 46% for a month. And one site's estimate can jump a hundredfold and drop back: mcpmarket.com went from 10 thousand to 3.4 million and back to 55 thousand in 2026, while Semrush showed steady growth and its ranking keywords rose the whole time. So a fall counts only when traffic and keywords fall together, held two months, measured against the controls; none of the twelve is flagged. Result: 11 of the 90 and 7 of the 31. Of the ten recent ones that visit data can check, nine lost their visits around the same month (one has bounced back since). The tenth is glama.ai: its US keywords fell from 20,535 to 432 in April 2026, Semrush shows the same fall, and its visits kept growing. It is unrelated to the Ahrefs mark: 4 of the 11 are marked, the same share as among all 90, so it carries something the mark does not. For 6 of the 11 no fall had been flagged before, and 2 of those 6 had come out ok. Across the 39 of the 90 that had 5,000 visits a month or more in July, 13 lost 40% or more of their visits in September 2026, nearly all AI tool directories; the median site kept 83%.
- **A fifth test, many pages and no rankings (2026-10-14)**: the sitemaps of the same 115 sites, read for free, against the keywords each ranks for on US Google. Pages per ranking keyword separates the Ahrefs mark at an AUC of 0.73 on its own, and it is the first signal that adds to the others: with visits, age and linking sites the cross-validated AUC rises from 0.746 to 0.776. As a rule, 1,000 or more pages for each ranking keyword (from 1,000 pages up) caught 14 of the 90, 10 of them marked; from 3,000 up, 5 of 5. Two skills directories among the 31 sit far out: 27,905 pages with no US ranking at all, and 146,670 with 219. A site in another language is left alone, since US rankings say little about it. The same test tried brand demand, whether anyone searches for the site's name, which an E-E-A-T talk proposes as a sign of authority: Google Ads volumes for the 115 names were weak (AUC 0.65) and made the combined model worse (0.731), and bare names collide with common words ("tool", "agent" and "crunch" read 450,000 to 1,000,000 a month). It was left out.
- **A sixth test, 0.4 against 0.5 (2026-10-15)**: the 90 Ahrefs-labelled sites, the 31 above and 16 sites around shared checkout links, each run with both versions (about $3.20 in all, one shared cache). On the 90 and the 31 the verdicts came out the same, but for two sites whose `site:` lookup failed in one of the runs: 0.5's new signals land on sites already marked caution. On the checkout set 0.5 turned 9 of 10 bad sites from caution to avoid (5 of 6 members of a link-selling network, 4 of 4 hacked sites carrying an injected checkout link) and flagged none of the 6 sites that merely cite those products. Three fixes followed. GoAnyAPI's September 2026 visits fell 46% to 76% for 16 of 59 sites with 5,000 a month or more, while their US Google search traffic from AIsa mostly held (one AI directory: visits down by two thirds, Google search traffic down 3%). So a fall in the newest month of the data is now a note until the next month confirms it: two of the 57 unmarked sites and two of the 31 (programminginsider.com, aijourn.com) went back to ok, and all 30 marked sites flagged before still are. The failed `site:` lookups were an "Internal SE Server Error." from AIsa's search after GoAnyAPI's own failure: such a lookup is now asked once more. And a home page that gives no answer is asked again 5 seconds later; the four unmarked sites called dead gave no answer from China or from an overseas exit either, hours apart, so those four verdicts stand. Each row now also carries its risk, 3 for each avoid finding and 1 for each caution: it ranks a marked site above an unmarked one 76% of the time, the verdict alone 62%. What remains: caution still covers 33 of the 57 unmarked sites, mostly through the spam score (19 of them at 40 or more) and through selling followed links (14). The second is a policy matter, not a misreading. The first is the next thing to settle, on a fresh set of labelled sites rather than these 90.
- **A seventh test, rules chosen on sites they had never seen (2026-10-16)**: the referring domains Ahrefs lists for two other sites of mine, an established one (872, 710 of them marked SPAM) and a new one (19), minus every site looked at before. Most of the established site's are link networks that link to everyone: 354 `.shop` sites named after SEO words, 131 long `.store` names, 84 numbered `.xyz`. A few of each went in, and the comparison leaves them out, since every rule catches them. That left 40 SPAM and 60 normal sites, run with 0.5 ($4.85 at list prices). One caution finding as a verdict flagged 43 of the 60 normal sites. The measure was fixed before the run (SPAM caught minus normal flagged, and it had to agree with the first 90), and the winner was: caution takes two caution findings, with the spam score counted from 50 rather than 40. It flags 21 of the 60 and still catches 28 of the 40; on the first 90 it flags 13 of 57 for 22 of 33. The 12 SPAM sites it lets through had one weak finding at most, and 11 of them under 1,500 visits a month; a single finding still shows under Why. Two more things showed. github.com and pypi.org came out as badge networks, because every project links them from its footer, so a site with 100,000 visits a month or more is no longer read as one. And `unproven` hit 19 normal sites and 16 SPAM here, against 6 and 17 on the first 90: new, small AI sites look like that without being spam. The Ahrefs mark has misses too: four sites it calls normal are plainly members of the networks above.
- **An eighth test, what the sites actually sent (2026-10-16)**: the young site's analytics for the last 30 days, set against its 90 referring domains. 29 of them sent at least one visit, 74 in all. Reach told them apart: 10 of the 14 rated high sent visits, 17 of the 38 rated medium, 2 of the 37 rated low. The verdict did not: the site that sent the most (10 visits) is a caution, a badge network that sells followed links. A verdict says what a link there risks; reach says what it can bring; read both. `--referrals` puts your own numbers beside them. The same day every home page was read again for its analytics and ads accounts: two pairs of sites shared an AdSense account, one of them two AI tool directories Ahrefs calls normal, now `same_owner`. Rule changes like these are checked with `scripts/regress.py`, which grades the saved results of all four labelled sets again in seconds; the labels stay out of the repository.
- **A ninth test, the established site's own analytics (2026-10-16)**: 90 days of referral sessions, with the screen sizes of known automation left out; they were few here, and the rest was 28% to 64% engaged. 9,094 sessions came from 135 sites, and only 26 of those are among the 872 referring domains Ahrefs lists: X (5,156) and GitHub (2,610) sent most, and links on X are not counted as backlinks at all. Of the 100 referring domains checked in the seventh test, 2 of the 7 rated high reach sent visits, 1 of the 20 medium and 1 of the 73 low; none of the 32 avoids sent any. One site Ahrefs marks SPAM sent 355 sessions, 64% of them engaged. What a link risks and what it brings are two questions, so the report now answers them in two columns, Link policy and Value.
- **"No page indexed in the last 30 days"**: a check passed around for paid directories. For the three it had called zombies, the same search on the same day found 9, 10 and 2 recent pages, and 4 of 14 calls timed out: a timeout read as a zero looks exactly like a zombie. Google also says `site:` counts are incomplete and new pages can take weeks. So `--recent` treats a failure as a failure, asks a zero twice, and only calls it a problem when the site's own sitemap shows new pages Google is not taking in.
- **What it cannot see**: of the five media sites that publish contributed posts, one states a fee on its pages. Whether the others charge cannot be read from their sites. A site that sells links in private is not caught by reading it.
