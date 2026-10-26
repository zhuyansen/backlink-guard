"""backlink-guard: check a link source before you submit to it, and watch your own link profile."""
import os
from pathlib import Path

__version__ = "0.8.0"
UA = f"Mozilla/5.0 (compatible; backlink-guard/{__version__}; +https://github.com/zhuyansen/backlink-guard)"


def state_dir() -> Path:
    """Where the log, the cache and the networks seen before are kept: BACKLINK_GUARD_STATE when set, ./state when
    it exists (a clone run from its own folder, as before 0.6), else ~/.backlink-guard, so an installed command
    keeps one log wherever it is run from."""
    if os.environ.get("BACKLINK_GUARD_STATE"):
        return Path(os.environ["BACKLINK_GUARD_STATE"])
    return Path("state") if Path("state").is_dir() else Path.home() / ".backlink-guard"
