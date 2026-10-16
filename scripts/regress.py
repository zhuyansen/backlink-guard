"""Grade saved check results again with the current rules, and compare them with labels.

    python scripts/regress.py [FOLDER]          every *.json set in FOLDER (default state/eval)
    python scripts/regress.py --save            also keep this run's grades as the baseline

A set is {"name", "about", "labels": {domain: "spam" | "normal"}, "leave_out": [domains not compared],
"batch_failed": [checks that failed for the whole batch], "rows": [rows as vet() returned them]}.
Each row is graded again with vet.finalize, so a change to a threshold or to the grading shows at
once and costs nothing; a change to how a signal is read needs the sites checked again. Labels such
as Ahrefs' SPAM mark come from your own accounts: keep them out of the repository (state/ is not
committed).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backlink_guard import vet  # noqa: E402

FLAGGED = {"avoid", "caution"}


def regrade(s: dict) -> dict[str, dict]:
    """The set's rows graded with the current rules; the accounts they share are matched again as in vet()."""
    failed = tuple(s.get("batch_failed", []))
    rows = [copy.deepcopy(r) for r in s["rows"]]
    for r in rows:
        r["flags"] = [f for f in r["flags"] if f["flag"] != "same_owner"]
    vet.shared_owners(rows)
    return {r.get("input") or r["domain"]: vet.finalize(r, () if r.get("skipped") else failed) for r in rows}


def auc(score: dict, pos: set, neg: set) -> float:
    pairs = [(score[a] > score[b]) + 0.5 * (score[a] == score[b]) for a in pos for b in neg]
    return sum(pairs) / len(pairs) if pairs else float("nan")


def summary(s: dict, rows: dict[str, dict]) -> list[str]:
    labels = {d: l for d, l in s.get("labels", {}).items() if d in rows and d not in set(s.get("leave_out", []))}
    spam, normal = {d for d, l in labels.items() if l == "spam"}, {d for d, l in labels.items() if l == "normal"}
    flagged = {d for d, r in rows.items() if r["grade"] in FLAGGED}
    lines = [f"== {s['name']}: {len(rows)} sites. {s.get('about', '')}".rstrip()]
    if spam or normal:
        caught, wrong = len(flagged & spam), len(flagged & normal)
        j = caught / max(1, len(spam)) - wrong / max(1, len(normal))
        lines.append(f"   SPAM caught {caught}/{len(spam)}, normal flagged {wrong}/{len(normal)}, "
                     f"J {j:.3f}, risk AUC {auc({d: r['risk'] for d, r in rows.items()}, spam, normal):.3f}")
    by = Counter((labels.get(d, "unlabelled"), r["grade"]) for d, r in rows.items())
    lines.append("   " + ", ".join(f"{l} {g} {n}" for (l, g), n in sorted(by.items())))
    acts = Counter((labels.get(d, "unlabelled"), r["action"]) for d, r in rows.items())
    lines.append("   action: " + ", ".join(f"{l} {a} {n}" for (l, a), n in sorted(acts.items())))
    return lines


def changes(rows: dict[str, dict], before: dict[str, str], labels: dict[str, str]) -> list[str]:
    out = []
    for d, r in sorted(rows.items()):
        if before.get(d) and before[d] != r["grade"]:
            found = [f["flag"] for f in r["flags"] if f["level"] != "note"] + [f"missing {m}" for m in r.get("missing", [])]
            out.append(f"   {d:<32} {labels.get(d, '-'):<8} {before[d]} -> {r['grade']}  {found}")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder", nargs="?", default="state/eval")
    p.add_argument("--save", action="store_true", help="keep this run's grades as the baseline")
    args = p.parse_args(argv)
    folder = Path(args.folder)
    sets = [json.loads(f.read_text()) for f in sorted(folder.glob("*.json")) if f.name != "baseline.json"]
    if not sets:
        raise SystemExit(f"no sets in {folder}")
    base_file = folder / "baseline.json"
    baseline = json.loads(base_file.read_text()) if base_file.exists() else {}
    new_base = {}
    for s in sets:
        rows = regrade(s)
        print("\n".join(summary(s, rows)))
        before = baseline.get(s["name"]) or {r.get("input") or r["domain"]: r["grade"] for r in s["rows"]}
        moved = changes(rows, before, s.get("labels", {}))
        print(f"   {len(moved)} changed against {'the baseline' if s['name'] in baseline else 'the grades when checked'}"
              + (":" if moved else ""))
        print("\n".join(moved[:40]) + (f"\n   … {len(moved) - 40} more" if len(moved) > 40 else "") if moved else "", end="")
        new_base[s["name"]] = {d: r["grade"] for d, r in rows.items()}
        print()
    if args.save:
        base_file.write_text(json.dumps(new_base, indent=1, sort_keys=True))
        print(f"baseline saved: {base_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
