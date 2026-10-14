"""Read the sites to check out of whatever list they came in: a text or Markdown note, a CSV,
a JSON export, or an Excel sheet (the paid backlink lists are often .xlsx). Every host name
found is kept once, in the order it first appears; file names and the like are skipped."""
from __future__ import annotations

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
