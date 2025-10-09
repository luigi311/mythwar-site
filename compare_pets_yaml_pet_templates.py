#!/usr/bin/env python3
"""
Compare a TS-shaped YAML dataset against an extracted TypeScript template.

YAML shape (dict keyed by camelCase IDs, mirroring TS):
antEater:
  name: "Ant Eater"
  image: "../../assets/monsters/ant_eater.gif"
  species: "Special"
  statRates:
    growthRate: { min: 1.149, max: 1.179 }
    sta: { min: 145, max: 145 }
    int: { min: 52, max: 52 }
    str: { min: 18, max: 18 }
    agi: { min: 69, max: 69 }
  build: { sta: 1, int: 1, str: 1, agi: 1 }
  skills: ["FrailtyI", "FrailtyII", "FrailtyIII", "FrailtyIV"]
  sources: []
  resist:
    dodgeRate: 5
    meleeResist: 30
    deathResist: 20

This script:
- Parses the YAML (dict keyed by pet ID).
- Parses ONLY top-level TS entries using a brace-balanced scanner.
- Compares species, statRates (growthRate + sta/int/str/agi), build, skills, resist.
- Reports numeric/string differences AND per-category missing keys.

Usage:
  python yaml_vs_ts_compare.py data.yaml template.ts > report.md
"""

from __future__ import annotations
import re
import sys
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

# ============== helpers ==============

def _to_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

_skill_fix = re.compile(r"MultiShot|Multishot", re.I)
def norm_skill(s: str) -> str:
    return _skill_fix.sub("MultiShot", s)

# ============== YAML loader ==============

def load_yaml_map(path: str) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required. pip install pyyaml")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("Expected YAML to be a dict keyed by camelCase pet IDs.")
    return data

# ============== TS balanced top-level parser ==============

@dataclass
class TsEntry:
    key: str
    orig_key: str
    name: Optional[str] = None
    species: Optional[str] = None
    gr_min: Optional[float] = None
    gr_max: Optional[float] = None
    stats: Dict[str, Tuple[Optional[float], Optional[float]]] = field(default_factory=dict)  # sta/int/str/agi -> (min,max)
    build: Dict[str, Optional[float]] = field(default_factory=dict)  # sta/int/str/agi
    skills: List[str] = field(default_factory=list)                  # e.g., FrailtyI
    resist: Dict[str, Optional[float]] = field(default_factory=dict) # flat keys

_name_re         = re.compile(r"name\s*:\s*['\"]([^'\"]+)['\"]")
_species_re      = re.compile(r"species\s*:\s*Species\.([A-Za-z]+)")
_growth_re       = re.compile(r"growthRate\s*:\s*\{[^}]*?min\s*:\s*([\d.]+)\s*,\s*max\s*:\s*([\d.]+)")
_stat_re         = re.compile(r"\b(sta|int|str|agi)\s*:\s*\{\s*min\s*:\s*([-+]?\d+(?:\.\d+)?)\s*,\s*max\s*:\s*([-+]?\d+(?:\.\d+)?)")
_skill_id_re     = re.compile(r"Skill\.([A-Za-z0-9]+)")
_resist_block_re = re.compile(r"resist\s*:\s*\{(.*?)\}", re.S)
_resist_kv_re    = re.compile(r"([A-Za-z]+[A-Za-z0-9]*)\s*:\s*([-+]?\d+(?:\.\d+)?)")
_build_block_re  = re.compile(r"build\s*:\s*{\s*(.*?)\s*}", re.S)
_build_kv_re     = re.compile(r"(sta|int|str|agi)\s*:\s*([-+]?\d+(?:\.\d+)?)")

def parse_ts(text: str) -> Dict[str, TsEntry]:
    entries: Dict[str, TsEntry] = {}

    i, n = 0, len(text)
    depth = 0
    in_str: Optional[str] = None
    esc = False
    base_depth: Optional[int] = None

    def capture_body(start_brace: int) -> Tuple[str, int]:
        k = start_brace + 1
        d = 1
        in_s2: Optional[str] = None
        esc2 = False
        while k < n and d > 0:
            c = text[k]
            if in_s2 is not None:
                if esc2:
                    esc2 = False
                elif c == "\\":
                    esc2 = True
                elif c == in_s2:
                    in_s2 = None
                k += 1
                continue
            if c in ("'", '"'):
                in_s2 = c; k += 1; continue
            if c == "{":
                d += 1; k += 1; continue
            if c == "}":
                d -= 1; k += 1; continue
            k += 1
        return text[start_brace + 1 : k - 1], k

    while i < n:
        ch = text[i]
        if in_str is not None:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == in_str: in_str = None
            i += 1; continue
        if ch in ("'", '"'):
            in_str = ch; i += 1; continue
        if ch == "{":
            depth += 1; i += 1; continue
        if ch == "}":
            depth = max(depth - 1, 0); i += 1; continue

        if ch.isalpha() or ch == "_":
            start = i
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            ident = text[start:j]
            k = j
            while k < n and text[k].isspace():
                k += 1
            if k < n and text[k] == ":":
                k += 1
                while k < n and text[k].isspace():
                    k += 1
                if k < n and text[k] == "{":
                    if base_depth is None:
                        base_depth = depth
                    if depth == base_depth:
                        body, next_i = capture_body(k)
                        e = TsEntry(key=norm_key(ident), orig_key=ident)
                        # extract fields
                        m = _name_re.search(body)
                        if m: e.name = m.group(1)
                        m = _species_re.search(body)
                        if m: e.species = m.group(1)
                        m = _growth_re.search(body)
                        if m:
                            e.gr_min = _to_float(m.group(1))
                            e.gr_max = _to_float(m.group(2))
                        for stat, smin, smax in _stat_re.findall(body):
                            e.stats[stat] = (_to_float(smin), _to_float(smax))
                        e.skills = [norm_skill(s) for s in _skill_id_re.findall(body)]
                        bm = _build_block_re.search(body)
                        if bm:
                            for k2, v in _build_kv_re.findall(bm.group(1)):
                                e.build[k2] = _to_float(v)
                        rm = _resist_block_re.search(body)
                        if rm:
                            for k2, v in _resist_kv_re.findall(rm.group(1)):
                                e.resist[k2] = _to_float(v)
                        entries[e.key] = e
                        i = next_i
                        continue
        i += 1

    return entries

# ============== comparison ==============

@dataclass
class Diff:
    field: str   # e.g., species, statRates.sta.min, build.sta, resist.pierce, skills
    yaml: Any
    ts: Any

@dataclass
class Missing:
    category: str  # e.g., resist, skills, statRates, build
    key: str       # sub-key (e.g., iceResist)
    side: str      # 'yaml' or 'ts'

STAT_KEYS = ["sta", "int", "str", "agi"]

# Canon list + union so we’ll also catch any extra keys
RESIST_KEYS_CANON = [
    "dodgeRate","meleeResist","pierce","pierceDamage","criticalRate","criticalDamage","comboRate","comboHit",
    "evilResist","flashResist","iceResist","fireResist","drainResist","poisonResist","chaosResist",
    "deathResist","stunResist","hypnotizeResist","frailtyResist",
]

def compare_entry(yaml_obj: Dict[str, Any], ts: TsEntry) -> Tuple[List[Diff], List[Missing]]:
    diffs: List[Diff] = []
    missing: List[Missing] = []

    # species
    y_species = yaml_obj.get("species")
    if y_species is not None and ts.species is not None and str(y_species) != str(ts.species):
        diffs.append(Diff("species", y_species, ts.species))

    # statRates.growthRate
    y_sr = yaml_obj.get("statRates") or {}
    y_gr = y_sr.get("growthRate") or {}
    y_gmin, y_gmax = y_gr.get("min"), y_gr.get("max")
    if y_gmin is not None and ts.gr_min is not None and float(y_gmin) != float(ts.gr_min):
        diffs.append(Diff("statRates.growthRate.min", y_gmin, ts.gr_min))
    if y_gmax is not None and ts.gr_max is not None and float(y_gmax) != float(ts.gr_max):
        diffs.append(Diff("statRates.growthRate.max", y_gmax, ts.gr_max))

    # statRates.{sta,int,str,agi}.min/max
    for s in STAT_KEYS:
        y_s = (y_sr.get(s) or {})
        y_min, y_max = y_s.get("min"), y_s.get("max")
        if s in ts.stats:
            tmin, tmax = ts.stats[s]
            if y_min is not None and tmin is not None and float(y_min) != float(tmin):
                diffs.append(Diff(f"statRates.{s}.min", y_min, tmin))
            if y_max is not None and tmax is not None and float(y_max) != float(tmax):
                diffs.append(Diff(f"statRates.{s}.max", y_max, tmax))
        else:
            if y_min is not None or y_max is not None:
                missing.append(Missing("statRates", s, "ts"))

    # build
    y_build = yaml_obj.get("build") or {}
    if y_build or ts.build:
        for k in STAT_KEYS:
            yv = y_build.get(k)
            tv = ts.build.get(k)
            if yv is None and tv is not None:
                missing.append(Missing("build", k, "yaml"))
            elif yv is not None and tv is None:
                missing.append(Missing("build", k, "ts"))
            elif yv is not None and tv is not None and float(yv) != float(tv):
                diffs.append(Diff(f"build.{k}", yv, tv))

    # skills — compare lists (order matters to mirror TS)
    y_sk = yaml_obj.get("skills") or []
    t_sk = ts.skills or []
    if y_sk and t_sk and list(y_sk) != list(t_sk):
        diffs.append(Diff("skills", y_sk, t_sk))
    elif not y_sk and t_sk:
        missing.append(Missing("skills", "list", "yaml"))
    elif y_sk and not t_sk:
        missing.append(Missing("skills", "list", "ts"))

    # resist — union of known keys and any present keys
    y_res = (yaml_obj.get("resist") or {})
    t_res = ts.resist or {}
    keys = set(RESIST_KEYS_CANON) | set(y_res.keys()) | set(t_res.keys())
    for k in sorted(keys):
        yv = y_res.get(k)
        tv = t_res.get(k)
        if yv is None and tv is None:
            continue
        if yv is None and tv is not None:
            missing.append(Missing("resist", k, "yaml"))
            continue
        if yv is not None and tv is None:
            missing.append(Missing("resist", k, "ts"))
            continue
        if float(yv) != float(tv):
            diffs.append(Diff(f"resist.{k}", yv, tv))

    return diffs, missing

# ============== report ==============

def render_report(yaml_map: Dict[str, Any], ts_map: Dict[str, TsEntry]) -> Tuple[str, int]:
    y_norm = { norm_key(k): (k, v) for k, v in yaml_map.items() }
    t_norm = { k: v for k, v in ts_map.items() }

    common = sorted(set(y_norm.keys()) & set(t_norm.keys()))
    only_yaml = sorted(set(y_norm.keys()) - set(t_norm.keys()))
    only_ts   = sorted(set(t_norm.keys()) - set(y_norm.keys()))

    out: List[str] = ["# YAML vs TypeScript Comparison\n"]
    total_diff = 0

    for nk in common:
        disp_key, y_obj = y_norm[nk]
        t_entry = t_norm[nk]
        diffs, missing = compare_entry(y_obj, t_entry)

        if not diffs and not missing:
            out.append(f"\n## {disp_key} ↔ {t_entry.orig_key} — ✅ No differences\n")
            continue

        out.append(f"\n## {disp_key} ↔ {t_entry.orig_key} — ❌ Differences\n")

        if diffs:
            total_diff += len(diffs)
            out.append("\n| Field | YAML | TS |\n|---|---:|---:|\n")
            for d in diffs:
                out.append(f"| {d.field} | {json.dumps(d.yaml, ensure_ascii=False)} | {json.dumps(d.ts, ensure_ascii=False)} |\n")

        if missing:
            by_cat: Dict[Tuple[str, str], List[str]] = {}
            for m in missing:
                by_cat.setdefault((m.category, m.side), []).append(m.key)
            out.append("\n**Missing keys (present on one side only):**\n")
            for (cat, side), keys in sorted(by_cat.items()):
                side_label = "in YAML" if side == "yaml" else "in TS"
                out.append(f"- {cat} missing {side_label}: {', '.join(sorted(set(keys)))}\n")

    if only_yaml:
        out.append("\n---\n\n**Present in YAML but not in the provided TS cut-out:**\\\n")
        out.append(", ".join([y_norm[k][0] for k in only_yaml]) + "\n")
    if only_ts:
        out.append("\n**Present in TS but not in YAML:**\\\n")
        out.append(", ".join([t_norm[k].orig_key for k in only_ts]) + "\n")

    return ("".join(out), total_diff)

# ============== main ==============

def main(argv: List[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    yaml_path, ts_path = argv[1], argv[2]

    yaml_map = load_yaml_map(yaml_path)
    with open(ts_path, "r", encoding="utf-8") as f:
        ts_text = f.read()
    ts_entries = parse_ts(ts_text)

    report, diff_count = render_report(yaml_map, ts_entries)
    print(report)
    return 1 if diff_count else 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
