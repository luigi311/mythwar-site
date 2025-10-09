# macros/shapeshift.py
from html import escape as _esc

def _safe(s): return _esc(str(s)).replace("|", "\\|")

def register(env, store):
    def shapeshift_bonuses_lookup(name):
        name_l = str(name or "").lower()
        for row in env.variables.get("shapeshift_bonuses", []):
            if str(row.get("name","")).lower() == name_l:
                return row
        return None

    @env.macro
    def shapeshift_index(group_by="location"):
        rows = env.variables.get("shapeshift", []) or []
        rows = [r for r in rows if isinstance(r, dict)]
        if group_by not in {"location","shapeshift","drop"}:
            group_by = "location"
        vals = sorted({str(r.get(group_by,"")).strip() for r in rows if r.get(group_by)},
                      key=lambda s: s.lower())
        return "_No entries_" if not vals else "\n".join(f"- {_esc(v)}" for v in vals)

    @env.macro
    def shapeshift_bonuses_table(filter_name=None, include_flat=True, compact=False,
                                 sort_by=("name","level"), show_name=True):
        data = env.variables.get("shapeshift_bonuses", []) or []
        rows = []
        fname = str(filter_name).lower() if filter_name else None

        for rec in data:
            name = str(rec.get("name","")).strip()
            if not name: continue
            if fname and name.lower() != fname: continue
            tiers = rec.get("tiers") or []
            flat = rec.get("flat") or []
            if tiers:
                for t in tiers:
                    rows.append({"name": name, "level": t.get("level"),
                                 "effects": list(map(str, t.get("effects") or [])), "kind": "tier"})
            elif include_flat and flat:
                rows.append({"name": name, "level": None,
                             "effects": list(map(str, flat)), "kind": "flat"})

        def _key(r):
            parts = []
            for k in sort_by or []:
                if k == "level":
                    v = r.get("level"); parts.append(10**9 if v in (None,"") else int(v))
                else:
                    parts.append(str(r.get(k,"")).lower())
            return tuple(parts)

        rows = sorted(rows, key=_key)
        if not rows: return "_No bonus data_"

        if not compact:
            header = "| Shapeshift | Lvl | Effects |\n|---|:--:|---|" if show_name else "| Lvl | Effects |\n|:--:|---|"
            lines = [header]
            for r in rows:
                lvl = "—" if r["level"] in (None,"") else str(r["level"])
                eff = "<br>".join(_esc(e) for e in r["effects"]) if r["effects"] else "—"
                lines.append(f"| **{_esc(r['name'])}** | {lvl} | {eff} |" if show_name else f"| {lvl} | {eff} |")
            return "\n".join(lines)

        bucket = {}
        for r in rows: bucket.setdefault(r["name"], []).append(r)
        header = "| Shapeshift | Effects |\n|---|---|" if show_name else "| Effects |\n|---|"
        lines = [header]
        for name in sorted(bucket.keys(), key=lambda s: s.lower()):
            parts = []
            tier_rows = sorted([x for x in bucket[name] if x["kind"]=="tier"],
                               key=lambda x: (10**9 if x["level"] in (None,"") else int(x["level"])))
            flat_rows = [x for x in bucket[name] if x["kind"]=="flat"]
            for x in tier_rows:
                eff = "<br>".join(_esc(e) for e in (x["effects"] or [])) or "—"
                parts.append(f"**L{x['level']}:** {eff}")
            for x in flat_rows:
                eff = "<br>".join(_esc(e) for e in (x["effects"] or [])) or "—"
                parts.append(f"**Flat:** {eff}")
            body = "<br><br>".join(parts) if parts else "—"
            lines.append(f"| **{_esc(name)}** | {body} |" if show_name else f"| {body} |")
        return "\n".join(lines)

    @env.macro
    def shapeshift_table(filter_shapeshift=None, filter_location=None, filter_drop=None,
                         group_by=None, sort_by=("shapeshift","location","drop")):
        rows = env.variables.get("shapeshift", []) or []
        rows = [r for r in rows if isinstance(r, dict)]

        def _eq(a,b): return str(a or "").lower()==str(b or "").lower()
        def _ok(r):
            if filter_shapeshift and not _eq(r.get("shapeshift"), filter_shapeshift): return False
            if filter_location and not _eq(r.get("location"), filter_location): return False
            if filter_drop and not _eq(r.get("drop"), filter_drop): return False
            return True

        rows = [r for r in rows if _ok(r)]
        if sort_by: rows = sorted(rows, key=lambda r: tuple(str(r.get(k,"")).lower() for k in sort_by))

        def _row(r):
            return "| " + " | ".join([_safe(r.get("shapeshift","")), _safe(r.get("location","")), _safe(r.get("drop",""))]) + " |"

        headers = ["Shapeshift Into","Location","SS Potion drop"]

        if group_by in {"shapeshift","location","drop"}:
            bucket = {}
            for r in rows: bucket.setdefault(r.get(group_by,""), []).append(r)
            parts = []
            for key in sorted(bucket.keys(), key=lambda s: str(s).lower()):
                parts.append(f"\n#### {_safe(key)}\n")
                body_rows = [_row(r) for r in bucket[key]]
                parts.append("| " + " | ".join(headers) + " |\n|" + "|".join([":--"]*len(headers)) + "|\n" + "\n".join(body_rows))
                if group_by in {"drop","shapeshift"}:
                    parts.append("\n" + shapeshift_bonuses_table(filter_name=key, show_name=False) + "\n")
            return "\n".join(parts).strip() or "_No entries_"

        body_rows = [_row(r) for r in rows]
        if not body_rows: return "_No entries_"
        return "| " + " | ".join(headers) + " |\n|" + "|".join([":--"]*len(headers)) + "|\n" + "\n".join(body_rows)
