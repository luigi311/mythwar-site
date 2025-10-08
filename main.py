import re
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

    # ----- Consumables -----
    consumables_path = docs_dir / "data" / "consumables.yaml"
    consumables = yaml.safe_load(consumables_path.read_text()) if consumables_path.exists() else []
    env.variables["consumables"] = consumables

    # ----- Equipment -----
    equip_path = docs_dir / "data" / "equipment.yaml"
    equipment = yaml.safe_load(equip_path.read_text()) if equip_path.exists() else []
    env.variables["equipment"] = equipment

    # ----- Shapeshift ----
    shapeshift_path = docs_dir / "data" / "shapeshift.yaml"
    shapeshift = (
        yaml.safe_load(shapeshift_path.read_text()) if shapeshift_path.exists() else []
    )
    env.variables["shapeshift"] = shapeshift

    # ----- Shapeshift Bonuses ----
    shapeshift_bonuses_path = docs_dir / "data" / "shapeshift_bonuses.yaml"
    shapeshift_bonuses = (
        yaml.safe_load(shapeshift_bonuses_path.read_text())
        if shapeshift_bonuses_path.exists()
        else []
    )
    env.variables["shapeshift_bonuses"] = shapeshift_bonuses

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

    def render_lists(items):
        if isinstance(items, str):
            return "**" + escape(items) + "**"
        return "<br>".join(f"**{s}**" for s in (items or []))

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
            f"| {render_lists(pet.get('skills'))} "
            f"| {stat_block(pet.get('stats'))} "
            f"| {render_lists(pet.get('source'))} "
            f"| {render_kv_block(pet.get('physical'))} "
            f"| {render_kv_block(pet.get('magical'))} "
            f"| {render_kv_block(pet.get('elemental'))} |"
        )
        return row.strip()

    # ---------------------------
    # Consumables rendering helpers
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
    def consumable_row(consumable):
        """
        Make one markdown table row for a consumable.
        Columns: Name | Price | Description | Source
        """
        name = escape(consumable.get("name", ""))
        price = _fmt_price(consumable.get("price"))
        desc = escape(consumable.get("description", ""))
        src = _fmt_source(consumable.get("source"))
        return f"| **{name}** | {price} | {desc} | {src} |"

    @env.macro
    def consumables_table(category=None, sort_by="name"):
        """
        Render a full markdown table for a category (or all).
        """
        its = env.variables.get("consumables", []) or []
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
            return "_No consumables yet_"
        header = "| Item | Price | Description | Source |\n|---|---:|---|---|"
        rows = [consumable_row(i) for i in its]
        return "\n".join([header, *rows])

    # ---------------------------
    # Equipment rendering helpers
    # ---------------------------

    def _slug(*parts):
        s = "-".join(p for p in parts if p)
        s = s.lower()
        s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
        return s

    @env.macro
    def gear_anchor_key(e):
        # unique + readable anchor id
        return _slug(
            e.get("slot", ""),
            e.get("race") or "any",
            e.get("gender") or "any",
            e.get("family", ""),
        )

    @env.macro
    def gear_index(
        slot=None, race=None, gender=None, include_empty=False, label_empty="(TBD)"
    ):
        eq = env.variables.get("equipment", [])

        def ok(e):
            return (
                (slot is None or str(e.get("slot")).lower() == str(slot).lower())
                and (race is None or str(e.get("race")).lower() == str(race).lower())
                and (
                    gender is None
                    or str(e.get("gender")).lower() == str(gender).lower()
                )
            )

        rows = [e for e in eq if ok(e)]
        if not rows:
            return "_No equipment found_"

        rows = sorted(
            rows,
            key=lambda e: (
                e.get("slot", ""),
                e.get("race") or "",
                e.get("gender") or "",
                e.get("family", ""),
            ),
        )

        out = [
            "| Family | Slot | Race | Gender | Bonus Type |",
            "|---|---|---|---|---|",
        ]

        for e in rows:
            tiers = e.get("tiers") or []
            if not tiers and not include_empty:
                continue
            first = tiers[0] if tiers else {}
            # Only show stat keys (bonus types), not numbers
            ex = ", ".join(first.get("bonus", {}).keys()) or label_empty
            anchor = gear_anchor_key(e)
            family_link = f"[**{escape(e.get('family', ''))}**](#{anchor})"
            out.append(
                f"| {family_link} | {escape(e.get('slot', ''))} | "
                f"{escape(e.get('race') or 'Any')} | {escape(e.get('gender') or 'Any')} | {escape(ex)} |"
            )

        if len(out) == 2:
            return "_No equipment with data yet_"
        return "\n".join(out)

    def _fmt_src(s):
        if not s:
            return "—"
        if isinstance(s, (list, tuple)):
            from html import escape

            return "<br>".join(escape(str(x)) for x in s)
        from html import escape

        return escape(str(s))

    def _fmt_tier_row(t):
        tier = escape(str(t.get("tier", "")))
        bonus = ", ".join(f"{k} +{v}" for k, v in (t.get("bonus") or {}).items()) or "—"
        req = ", ".join(f"{k} {v}" for k, v in (t.get("req") or {}).items()) or "—"
        src = _fmt_src(t.get("source"))
        return f"| {tier} | {escape(bonus)} | {escape(req)} | {src} |"

    @env.macro
    def gear_family_table_by_obj(e, slot=True, race=True, gender=True):
        """Render a plain Markdown table for one equipment family,
        with optional slot/race/gender display in the header."""
        anchor = gear_anchor_key(e)

        # Build optional parts
        parts = []
        if slot:
            parts.append(e.get("slot") or "Any")
        if race:
            parts.append(e.get("race") or "Any")
        if gender:
            parts.append(e.get("gender") or "Any")

        # Build header string (omit () if no parts)
        if parts:
            header_meta = " ".join(str(p) for p in parts)
            header = f"<a id='{anchor}'></a>\n### {escape(e.get('family', ''))} <small>({escape(header_meta)})</small>\n"
        else:
            header = f"<a id='{anchor}'></a>\n### {escape(e.get('family', ''))}\n"

        # Table
        table_md = "| Tier | Bonus | Requirements | Source |\n|---|---|---|---|"
        rows_md = "\n".join(_fmt_tier_row(t) for t in (e.get("tiers") or []))
        if not rows_md:
            rows_md = "| — | — | — | — |"

        body = table_md + "\n" + rows_md
        body += "\n\n[Back to top](#equipment)"

        return header + "\n" + body

    @env.macro
    def gear_family_table(key_or_obj):
        """Backward compatible wrapper: accept key or object; renders plain table."""
        all_eq = env.variables.get("equipment", [])
        if isinstance(key_or_obj, dict):
            e = key_or_obj
        else:
            e = next((x for x in all_eq if x.get("key") == key_or_obj), None)
        if not e:
            return "_Unknown equipment key_"
        return gear_family_table_by_obj(e)

    def _gear_filter(eq, slot=None, race=None, gender=None, set_name=None):
        def ok(e):
            return (
                (slot is None or str(e.get("slot")).lower() == str(slot).lower())
                and (race is None or str(e.get("race")).lower() == str(race).lower())
                and (
                    gender is None
                    or str(e.get("gender")).lower() == str(gender).lower()
                )
                and (
                    set_name is None
                    or str(e.get("set", "")).lower() == str(set_name).lower()
                )
            )

        return [e for e in eq if ok(e)]

    @env.macro
    def gear_index_by_set(
        set_name, slot=None, include_empty=False, label_empty="(TBD)"
    ):
        """Index like gear_index, but limited to a set (e.g., 'Armor of Dream')."""
        eq = env.variables.get("equipment", [])
        rows = _gear_filter(eq, slot=slot, set_name=set_name)
        if not rows:
            return "_No equipment found_"
        rows = sorted(
            rows,
            key=lambda e: (
                e.get("slot", ""),
                e.get("race") or "",
                e.get("gender") or "",
                e.get("family", ""),
            ),
        )
        out = [
            "| Family | Slot | Race | Gender | Example Bonus (Tier +1) |",
            "|---|---|---|---|---|",
        ]
        for e in rows:
            tiers = e.get("tiers") or []
            if not tiers and not include_empty:
                continue
            first = tiers[0] if tiers else {}
            ex = (
                ", ".join(first.get("bonus", {}).keys()) or label_empty
            )  # show bonus types only
            anchor = gear_anchor_key(e)
            family_link = f"[**{escape(e.get('family', ''))}**](#{anchor})"
            out.append(
                f"| {family_link} | {escape(e.get('slot', ''))} | "
                f"{escape(e.get('race') or 'Any')} | {escape(e.get('gender') or 'Any')} | {escape(ex)} |"
            )
        if len(out) == 2:
            return "_No equipment with data yet_"
        return "\n".join(out)

    @env.macro
    def gear_tables_by_set(set_name, slot=True, race=True, gender=True):
        """Render all families for a set, with optional slot/race/gender header fields."""
        eq = env.variables.get("equipment", [])
        rows = [e for e in eq if str(e.get("set", "")).lower() == str(set_name).lower()]
        if not rows:
            return "_No equipment found_"
        rows = sorted(
            rows,
            key=lambda e: (
                e.get("slot", ""),
                e.get("race") or "",
                e.get("gender") or "",
                e.get("family", ""),
            ),
        )

        parts = []
        for e in rows:
            parts.append(
                gear_family_table_by_obj(e, slot=slot, race=race, gender=gender)
            )
            parts.append("")
        return "\n".join(parts).strip()

    # ---------------------------
    # Shapeshift rendering helpers
    # ---------------------------

    def _safe(s):
        return escape(str(s)).replace("|", "\\|")

    def _render_md_table(items, headers):
        lines = [
            "| " + " | ".join(headers) + " |",
            "|" + "|".join([":--"] * len(headers)) + "|",
        ]
        lines.extend(items)
        return "\n".join(lines)

    @env.macro
    def shapeshift_table(
        filter_shapeshift=None,
        filter_location=None,
        filter_drop=None,
        group_by=None,
        sort_by=("shapeshift", "location", "drop"),
    ):
        """
        Render the Shapeshift → Location → SS Potion table from data/shapeshift.yaml.

        Parameters:
        - filter_shapeshift: only rows matching this shapeshift (case-insensitive)
        - filter_location: only rows matching this location (case-insensitive)
        - filter_drop: only rows matching this potion/drop (case-insensitive)
        - group_by: None | "shapeshift" | "location" | "drop"
        - sort_by: tuple/list of keys to sort by
        """
        rows = env.variables.get("shapeshift", []) or []
        # keep only dict rows
        rows = [r for r in rows if isinstance(r, dict)]

        def _eq(a, b):
            return str(a or "").lower() == str(b or "").lower()

        def _ok(r):
            if filter_shapeshift and not _eq(r.get("shapeshift"), filter_shapeshift):
                return False
            if filter_location and not _eq(r.get("location"), filter_location):
                return False
            if filter_drop and not _eq(r.get("drop"), filter_drop):
                return False
            return True

        rows = [r for r in rows if _ok(r)]

        if sort_by:

            def kf(r):
                return tuple(str(r.get(k, "")).lower() for k in sort_by)

            rows = sorted(rows, key=kf)

        def _safe(s):  # local small helper
            from html import escape

            return escape(str(s)).replace("|", "\\|")

        def _row(r):
            return (
                "| "
                + " | ".join(
                    [
                        _safe(r.get("shapeshift", "")),
                        _safe(r.get("location", "")),
                        _safe(r.get("drop", "")),
                    ]
                )
                + " |"
            )

        headers = ["Shapeshift Into", "Location", "SS Potion drop"]

        # Grouped rendering (NOW supports "drop")
        if group_by in {"shapeshift", "location", "drop"}:
            bucket = {}
            for r in rows:
                key = r.get(group_by, "")
                bucket.setdefault(key, []).append(r)

            parts = []
            for key in sorted(bucket.keys(), key=lambda s: str(s).lower()):
                parts.append(f"\n#### {_safe(key)}\n")
                body_rows = [_row(r) for r in bucket[key]]
                parts.append(
                    "| " + " | ".join(headers) + " |\n"
                    "|"
                    + "|".join([":--"] * len(headers))
                    + "|\n"
                    + "\n".join(body_rows)
                )
                if group_by == "drop":
                    # 'key' here is the potion name; show its shapeshift bonuses
                    parts.append(
                        "\n"
                        + shapeshift_bonuses_table(filter_name=key, show_name=False)
                        + "\n"
                    )
                elif group_by == "shapeshift":
                    parts.append(
                        "\n"
                        + shapeshift_bonuses_table(filter_name=key, show_name=False)
                        + "\n"
                    )

            return "\n".join(parts).strip() or "_No entries_"

        # Flat table
        body_rows = [_row(r) for r in rows]
        if not body_rows:
            return "_No entries_"
        return (
            "| " + " | ".join(headers) + " |\n"
            "|" + "|".join([":--"] * len(headers)) + "|\n" + "\n".join(body_rows)
        )

    @env.macro
    def shapeshift_index(group_by="location"):
        """
        Quick index grouped by 'location', 'shapeshift', or 'drop'.
        """
        rows = env.variables.get("shapeshift", []) or []
        rows = [r for r in rows if isinstance(r, dict)]
        if group_by not in {"location", "shapeshift", "drop"}:
            group_by = "location"

        vals = sorted(
            {str(r.get(group_by, "")).strip() for r in rows if r.get(group_by)},
            key=lambda s: s.lower(),
        )
        if not vals:
            return "_No entries_"
        from html import escape

        return "\n".join(f"- {escape(v)}" for v in vals)

    def _ssb_lookup(name):
        name_l = str(name or "").lower()
        for row in env.variables.get("shapeshift_bonuses", []):
            if str(row.get("name", "")).lower() == name_l:
                return row
        return None

    @env.macro
    def shapeshift_bonuses_table(
        filter_name=None,  # exact name match (optional)
        include_flat=True,  # include flat-only entries like Aquarius, etc.
        compact=False,  # False = one row per tier; True = tiers stacked per form
        sort_by=("name", "level"),  # default sort
        show_name=True,  # include the "Shapeshift" name column or not
    ):
        """
        Render the shapeshift bonuses table.

        Columns:
        - compact=False:
            show_name=True  ->  Shapeshift | Lvl | Effects
            show_name=False ->           Lvl | Effects
        - compact=True:
            show_name=True  ->  Shapeshift | Effects
            show_name=False ->            Effects

        Examples:
        {{ shapeshift_bonuses_table() }}
        {{ shapeshift_bonuses_table(compact=True) }}
        {{ shapeshift_bonuses_table(filter_name="Phoenix", compact=True, show_name=False) }}
        {{ shapeshift_bonuses_table(include_flat=False, show_name=False) }}
        """
        data = env.variables.get("shapeshift_bonuses", []) or []

        # normalize & filter
        rows = []
        fname = str(filter_name).lower() if filter_name else None

        for rec in data:
            name = str(rec.get("name", "")).strip()
            if not name:
                continue
            if fname and name.lower() != fname:
                continue

            tiers = rec.get("tiers") or []
            flat = rec.get("flat") or []

            if tiers:
                for t in tiers:
                    lvl = t.get("level")
                    eff = t.get("effects") or []
                    rows.append(
                        {
                            "name": name,
                            "level": lvl,
                            "effects": list(map(str, eff)),
                            "kind": "tier",
                        }
                    )
            elif include_flat and flat:
                rows.append(
                    {
                        "name": name,
                        "level": None,
                        "effects": list(map(str, flat)),
                        "kind": "flat",
                    }
                )

        # sorting
        def _key(r):
            parts = []
            for k in sort_by or []:
                if k == "level":
                    v = r.get("level")
                    parts.append((1e9 if v in (None, "") else int(v)))
                else:
                    parts.append(str(r.get(k, "")).lower())
            return tuple(parts)

        rows = sorted(rows, key=_key)

        # rendering helpers
        def _esc(s):
            from html import escape

            return escape(str(s)).replace("|", "\\|")

        if not rows:
            return "_No bonus data_"

        if not compact:
            # Detailed (one row per tier)
            if show_name:
                header = "| Shapeshift | Lvl | Effects |\n|---|:--:|---|"
            else:
                header = "| Lvl | Effects |\n|:--:|---|"
            lines = [header]
            for r in rows:
                lvl = "—" if r["level"] in (None, "") else str(r["level"])
                eff = (
                    "<br>".join(_esc(e) for e in r["effects"]) if r["effects"] else "—"
                )
                if show_name:
                    lines.append(f"| **{_esc(r['name'])}** | {lvl} | {eff} |")
                else:
                    lines.append(f"| {lvl} | {eff} |")
            return "\n".join(lines)

        # Compact (one row per form, tiers stacked)
        bucket = {}
        for r in rows:
            bucket.setdefault(r["name"], []).append(r)

        if show_name:
            header = "| Shapeshift | Effects |\n|---|---|"
        else:
            header = "| Effects |\n|---|"
        lines = [header]

        for name in sorted(bucket.keys(), key=lambda s: s.lower()):
            parts = []
            tier_rows = [x for x in bucket[name] if x["kind"] == "tier"]
            flat_rows = [x for x in bucket[name] if x["kind"] == "flat"]

            tier_rows = sorted(
                tier_rows,
                key=lambda x: (1e9 if x["level"] in (None, "") else int(x["level"])),
            )
            for x in tier_rows:
                eff = "<br>".join(_esc(e) for e in (x["effects"] or [])) or "—"
                parts.append(f"**L{x['level']}:** {eff}")

            for x in flat_rows:
                eff = "<br>".join(_esc(e) for e in (x["effects"] or [])) or "—"
                parts.append(f"**Flat:** {eff}")

            body = "<br><br>".join(parts) if parts else "—"
            if show_name:
                lines.append(f"| **{_esc(name)}** | {body} |")
            else:
                lines.append(f"| {body} |")

        return "\n".join(lines)
