import json
from pathlib import Path
from config import SHARED_FOLDER

FAV_FILE = SHARED_FOLDER / ".cache" / "favorites.json"

def load_favorites() -> list[str]:
    """Load list of favorite filenames (relative to SHARED_FOLDER)."""
    if not FAV_FILE.exists():
        return []
    try:
        with open(FAV_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_favorites(favs: list[str]):
    """Save list of favorite filenames."""
    FAV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FAV_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, indent=4)

def toggle_favorite(filename: str) -> bool:
    """Add/remove a file from favorites. Returns new state."""
    favs = load_favorites()
    if filename in favs:
        favs.remove(filename)
        res = False
    else:
        favs.append(filename)
        res = True
    save_favorites(favs)
    return res

def is_favorite(filename: str) -> bool:
    """Check if a file is favorited."""
    return filename in load_favorites()

def list_favorites_details() -> list[dict]:
    """Return full file info for all favorited files."""
    from file_manager import _file_info
    fav_names = load_favorites()
    details = []
    for name in fav_names:
        path = SHARED_FOLDER / name
        if path.exists():
            try:
                details.append(_file_info(path))
            except Exception:
                pass
    return details
