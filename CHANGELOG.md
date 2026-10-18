# Changelog

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
