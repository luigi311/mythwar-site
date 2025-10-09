from pathlib import Path
import yaml

def _read_yaml(path: Path, default):
    return yaml.safe_load(path.read_text()) if path.exists() else default

def _pets_to_list(pets_raw):
    """Accepts dict OR list. Returns a list of pet dicts, each with a 'key' field."""
    if isinstance(pets_raw, dict):
        out = []
        for k, v in pets_raw.items():
            item = dict(v or {})
            item.setdefault("key", k)
            out.append(item)
        # Sort by display name when present, else by key
        out.sort(key=lambda p: (str(p.get("name", "")) or str(p.get("key", ""))).lower())
        return out
    return list(pets_raw or [])

def load_all(docs_dir: Path):
    data_dir = docs_dir / "data"
    pets_raw = _read_yaml(data_dir / "pets.yaml", {})
    return {
        "pets": _pets_to_list(pets_raw),
        "consumables": _read_yaml(data_dir / "consumables.yaml", []),
        "equipment": _read_yaml(data_dir / "equipment.yaml", []),
        "shapeshift": _read_yaml(data_dir / "shapeshift.yaml", []),
        "shapeshift_bonuses": _read_yaml(data_dir / "shapeshift_bonuses.yaml", []),
    }
