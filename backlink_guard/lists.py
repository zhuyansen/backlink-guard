"""Read the sites to check out of whatever list they came in: a text or Markdown note, a CSV,
a JSON export, or an Excel sheet (the paid backlink lists are often .xlsx). Every host name
found is kept once, in the order it first appears; file names and the like are skipped."""
from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path

from . import page

HOST = re.compile(r"(?<![@\w.-])(?:https?://)?((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})(?![\w-])", re.I)
NOT_TLDS = {"json", "py", "md", "html", "htm", "csv", "xlsx", "xls", "js", "mjs", "ts", "txt", "png", "jpg", "jpeg",
            "gif", "svg", "pdf", "zip", "yml", "yaml", "toml", "sqlite3", "log", "xml", "css"}


def text_of(path: Path) -> str:
    if path.suffix.lower() != ".xlsx":
        return path.read_text(errors="replace")
    with zipfile.ZipFile(path) as book:     # shared strings and sheets are XML; the names sit in their text
        parts = [n for n in book.namelist() if n.startswith("xl/") and n.endswith(".xml")]
        return " ".join(re.sub(r"<[^>]+>", " ", book.read(n).decode("utf-8", "replace")) for n in parts)


def domains(text: str) -> list[str]:
    seen, out = set(), []
    for m in HOST.finditer(text):
        host = m.group(1).lower()
        if host.rsplit(".", 1)[-1] in NOT_TLDS:
            continue
        site = page.site(host)
        if site not in seen:
            seen.add(site)
            out.append(site)
    return out


def read(path: str) -> list[str]:
    return domains(text_of(Path(path)))


SOURCE_HEAD = re.compile(r"source|domain|referr|site", re.I)
COUNT_HEAD = re.compile(r"session|visit|user|click", re.I)


def columns(header: list[str]) -> tuple[int, int] | None:
    """(source column, count column) of a header row: "Session source" names the sources, so the count is
    another column ("Sessions"), not it."""
    src = next((i for i, c in enumerate(header) if SOURCE_HEAD.search(c)), None)
    cnt = next((i for i, c in enumerate(header) if i != src and COUNT_HEAD.search(c)), None)
    return (src, cnt) if src is not None and cnt is not None else None


def referrals(path: str) -> dict[str, int]:
    """{site: visits} from an analytics export of where your visitors came from: a CSV such as GA4's Traffic
    acquisition report (Session source, Sessions; its "#" lines are skipped), or JSON {"site": visits}. Rows of
    one site are added up; "producthunt.com / referral" counts for producthunt.com; "(direct)" and "google" are
    not sites and are left out."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        pairs = list(json.loads(p.read_text()).items())
    else:
        rows = list(csv.reader(l for l in p.read_text(errors="replace").splitlines() if l.strip() and not l.startswith("#")))
        head = next(((i, cols) for i, r in enumerate(rows) if (cols := columns(r))), None)
        if head is None:
            raise ValueError(f"{path}: no column of sources and no column of sessions or visits")
        (i, (src, cnt)) = head
        pairs = [(r[src], r[cnt]) for r in rows[i + 1:] if len(r) > max(src, cnt)]
    out: dict[str, int] = {}
    for source, count in pairs:
        host = HOST.search(str(source).split(" / ")[0].strip())
        n = int(float(str(count).replace(",", "") or 0)) if re.fullmatch(r"[\d,.]+", str(count).strip() or "x") else 0
        if host and n:
            site = page.site(host.group(1).lower())
            out[site] = out.get(site, 0) + n
    return out
