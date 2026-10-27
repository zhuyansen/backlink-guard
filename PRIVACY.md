# Privacy

backlink-guard runs on your machine: the command line, the skill and the MCP server alike. Its author runs no server and collects nothing from it: no account, no telemetry, no analytics.

## What it reads

- The pages you ask it to check: a site's home, submit and pricing pages, its sitemaps, a page you want verified, and the redirects they lead to.
- Public sources about those sites: the Wayback Machine's first copy (archive.org), the suggestions Google Trends gives for a site's name, Google's Search Status feed of ranking updates, and the shared list of spam link sources on GitHub ([backlink-spam-list](https://github.com/zhuyansen/backlink-spam-list)).
- With `vet --newcomers` (and the free vets of `competitors --early`): a source's newest sitemap pages, and the public registration date of each site they link to (RDAP: rdap.org and the registry it points to).

## What it sends, and where

Paid checks send the domains, page addresses, keywords and questions you ask about, and nothing else from your machine, to the data provider whose key you set:

- Glasser (`api.glasser.ai`), with `GLASSER_API_KEY`
- AIsa (`tools.aisa.one`, `api.aisa.one`), with `AISA_API_KEY`, or the key the AIsa CLI stored in `~/.aisa/key` when that is not set
- GoAnyAPI (`api.goanyapi.com`), with `GOANYAPI_API_KEY`

Each key goes only to its own provider. What a provider keeps of a request is governed by that provider's own privacy policy. Without a key, the checks that need it are skipped, or stop with a message naming the key.

## What it keeps, on your machine only

In `BACKLINK_GUARD_STATE` when set, else `~/.backlink-guard` (in Claude Code, the plugin's own data folder):

- your submission log (`ledger.jsonl`), written only when you log a submission
- a cache of the providers' answers, so a repeated check costs nothing
- the page templates and the analytics or ads accounts of the sites checked before, so a network of sites shows up across runs

Delete the folder to remove all of it. Keys are never written there: they come from your environment, and in Claude Code from the plugin's settings, which keep them in the system keychain.

## Contact

Questions or a problem: [open an issue](https://github.com/zhuyansen/backlink-guard/issues).
