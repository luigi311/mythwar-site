import yaml
import math
import statistics
from pathlib import Path
from html import escape


def define_env(env):
    docs_dir = Path(env.conf["docs_dir"])

    # ----- Pets -----
    data_path = docs_dir / "data" / "pets.yaml"
    pets = yaml.safe_load(data_path.read_text())
    env.variables["pets"] = pets

    # ----- Items -----
    items_path = docs_dir / "data" / "items.yaml"
    if items_path.exists():
        items = yaml.safe_load(items_path.read_text()) or []
    else:
        items = []
    env.variables["items"] = items

    # ---------------------------
    # Thresholds derivation
    # ---------------------------

    # Optional hard overrides per stat (leave empty or add entries like "Sta": [60,100,130,140])
    OVERRIDE_THRESHOLDS = {
        # "Sta": [60, 100, 130, 140],
        # "Int": [60, 80, 100, 120],
        # "Str": [15, 30, 60, 90],
        # "Agi": [60, 80, 100, 120],
    }

    # Which stats to derive thresholds for:
    STATS_TO_DERIVE = ["Sta", "Int", "Str", "Agi"]

    def _to_number(x):
        """Best effort: turn strings like '52' or '52.0' into int; keep ints; ignore others."""
        if isinstance(x, (int, float)):
            return int(x)
        if isinstance(x, str):
            try:
                f = float(x.strip())
                return int(f)
            except Exception:
                return None
        return None

    def _collect_values(pets, stat_name):
        vals = []
        for p in pets or []:
            v = (p.get("stats") or {}).get(stat_name)
            v = _to_number(v)
            if v is not None:
                vals.append(v)
        return vals

    def derive_thresholds(values):
        """
        Return 4 cutoffs [t1,t2,t3,t4] for 1..4★.
        Uses quartiles; t4 is max(values) so top values get 4★.
        Falls back gracefully if data is tiny or flat.
        """
        if not values:
            return None
        values = sorted(values)
        unique_vals = sorted(set(values))
        vmax = unique_vals[-1]
        # If all values equal -> put everything at 1★ and reserve 4★ for vmax
        if len(unique_vals) == 1:
            v = unique_vals[0]
            return [v, v, v, v]

        try:
            # statistics.quantiles returns Q1,Q2,Q3 for n=4
            q1, q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
            # Ensure monotonic non-decreasing ints
            t1 = int(math.floor(q1))
            t2 = max(t1, int(math.floor(q2)))
            t3 = max(t2, int(math.floor(q3)))
            t4 = vmax
            return [t1, t2, t3, t4]
        except Exception:
            # Fallback: simple linear splits across range
            vmin = values[0]
            span = max(1, vmax - vmin)
            t1 = vmin + span // 4
            t2 = vmin + span // 2
            t3 = vmin + (3 * span) // 4
            t4 = vmax
            return [t1, t2, t3, t4]

    # Build the thresholds map
    STAT_THRESHOLDS = {}
    for name in STATS_TO_DERIVE:
        if name in OVERRIDE_THRESHOLDS and OVERRIDE_THRESHOLDS[name]:
            STAT_THRESHOLDS[name] = OVERRIDE_THRESHOLDS[name]
        else:
            vals = _collect_values(pets, name)
            t = derive_thresholds(vals)
            if t:
                STAT_THRESHOLDS[name] = t

    # Expose for debugging if you want to print them in a page
    env.variables["stat_thresholds"] = STAT_THRESHOLDS

    # ---------------------------
    # Rendering helpers
    # ---------------------------

    def starify(value, stat_name=None, default_thresholds=(20, 50, 100, 140)):
        """
        0★ -> '☆' (single hollow)
        1..4★ -> that many '★'
        """
        v = _to_number(value)
        if v is None:
            return str(value)

        thresholds = STAT_THRESHOLDS.get(stat_name, default_thresholds)
        stars = sum(1 for t in thresholds if v >= t)
        return "☆" if stars == 0 else "★" * stars

    def render_skills(skills):
        return "<br>".join(f"**{s}**" for s in (skills or []))

    def render_kv_block(d):
        return "<br>".join(f"{k} **{v}**" for k, v in (d or {}).items())

    def stat_block(stats):
        out = []
        for k, v in (stats or {}).items():
            out.append(f"{k}: {starify(v, stat_name=k)} (**{v}**)")
        return "<br>".join(out)

    @env.macro
    def pet_row(pet):
        row = (
            f"| **{pet['name']}** <img src='{pet['image']}'/> "
            f"| {pet['species']} "
            f"| **{pet['gr']}** "
            f"| {render_skills(pet.get('skills'))} "
            f"| {stat_block(pet.get('stats'))} "
            f"| {pet.get('source', '')} "
            f"| {render_kv_block(pet.get('physical'))} "
            f"| {render_kv_block(pet.get('magical'))} "
            f"| {render_kv_block(pet.get('elemental'))} |"
        )
        return row.strip()

    # ---------------------------
    # Item rendering helpers
    # ---------------------------
    def _fmt_price(p):
        if p is None or p == "":
            return "—"
        try:
            return f"{int(p):,} gold"
        except Exception:
            # allow things like "Item Mall" or non-gold notes if you ever use them in price
            return escape(str(p))

    def _fmt_source(src):
        if not src:
            return "—"
        if isinstance(src, (list, tuple)):
            return "<br>".join(escape(str(s)) for s in src)
        return escape(str(src))

    @env.macro
    def item_row(item):
        """
        Make one markdown table row for an item.
        Columns: Name | Price | Description | Source
        """
        name = escape(item.get("name", ""))
        price = _fmt_price(item.get("price"))
        desc = escape(item.get("description", ""))
        src = _fmt_source(item.get("source"))
        return f"| **{name}** | {price} | {desc} | {src} |"

    @env.macro
    def items_table(category=None, sort_by="name"):
        """
        Render a full markdown table for a category (or all).
        """
        its = env.variables.get("items", []) or []
        if category:
            its = [
                i
                for i in its
                if str(i.get("category", "")).lower() == str(category).lower()
            ]

        # sort robustly
        def _key(i):
            v = i.get(sort_by)
            if v is None:
                return ""
            return str(v)

        its = sorted(its, key=_key)
        if not its:
            return "_No items yet_"
        header = "| Item | Price | Description | Source |\n|---|---:|---|---|"
        rows = [item_row(i) for i in its]
        return "\n".join([header, *rows])
