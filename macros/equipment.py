import re
from html import escape as _esc

def _slug(*parts):
    s = "-".join(p for p in parts if p)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

def _fmt_src(s):
    if not s:
        return "—"
    if isinstance(s, (list, tuple)):
        from html import escape
        return "<br>".join(escape(str(x)) for x in s)
    from html import escape
    return escape(str(s))

def _fmt_tier_row(t):
    tier = _esc(str(t.get("tier","")))
    bonus = ", ".join(f"{k} +{v}" for k,v in (t.get("bonus") or {}).items()) or "—"
    req = ", ".join(f"{k} {v}" for k,v in (t.get("req") or {}).items()) or "—"
    src = _fmt_src(t.get("source"))
    return f"| {tier} | {_esc(bonus)} | {_esc(req)} | {src} |"

def _gear_filter(eq, slot=None, race=None, gender=None, set_name=None):
    def ok(e):
        return (
            (slot is None   or str(e.get("slot")).lower()==str(slot).lower()) and
            (race is None   or str(e.get("race")).lower()==str(race).lower()) and
            (gender is None or str(e.get("gender")).lower()==str(gender).lower()) and
            (set_name is None or str(e.get("set","")).lower()==str(set_name).lower())
        )
    return [e for e in eq if ok(e)]

def register(env, store):
    @env.macro
    def gear_anchor_key(e):
        return _slug(e.get("slot",""), e.get("race") or "any",
                     e.get("gender") or "any", e.get("family",""))

    @env.macro
    def gear_index(slot=None, race=None, gender=None, include_empty=False, label_empty="(TBD)"):
        eq = env.variables.get("equipment", [])
        rows = [e for e in eq if (
            (slot   is None or str(e.get("slot")).lower()==str(slot).lower()) and
            (race   is None or str(e.get("race")).lower()==str(race).lower()) and
            (gender is None or str(e.get("gender")).lower()==str(gender).lower())
        )]
        if not rows:
            return "_No equipment found_"
        rows = sorted(rows, key=lambda e: (e.get("slot",""), e.get("race") or "", e.get("gender") or "", e.get("family","")))
        out = ["| Family | Slot | Race | Gender | Bonus Type |","|---|---|---|---|---|"]
        for e in rows:
            tiers = e.get("tiers") or []
            if not tiers and not include_empty:
                continue
            first = tiers[0] if tiers else {}
            ex = ", ".join(first.get("bonus",{}).keys()) or label_empty
            anchor = gear_anchor_key(e)
            family_link = f"[**{_esc(e.get('family',''))}**](#{anchor})"
            out.append(f"| {family_link} | {_esc(e.get('slot',''))} | {_esc(e.get('race') or 'Any')} | {_esc(e.get('gender') or 'Any')} | {_esc(ex)} |")
        return "\n".join(out) if len(out) > 2 else "_No equipment with data yet_"

    @env.macro
    def gear_family_table_by_obj(e, slot=True, race=True, gender=True):
        anchor = gear_anchor_key(e)
        parts = []
        if slot:
            parts.append(e.get("slot") or "Any")
        if race:
            parts.append(e.get("race") or "Any")
        if gender:
            parts.append(e.get("gender") or "Any")
        if parts:
            header_meta = " ".join(str(p) for p in parts)
            header = f"<a id='{anchor}'></a>\n### {_esc(e.get('family',''))} <small>({_esc(header_meta)})</small>\n"
        else:
            header = f"<a id='{anchor}'></a>\n### {_esc(e.get('family',''))}\n"
        table_md = "| Tier | Bonus | Requirements | Source |\n|---|---|---|---|"
        rows_md = "\n".join(_fmt_tier_row(t) for t in (e.get("tiers") or [])) or "| — | — | — | — |"
        body = table_md + "\n" + rows_md + "\n\n[Back to top](#equipment)"
        return header + "\n" + body

    @env.macro
    def gear_family_table(key_or_obj):
        all_eq = env.variables.get("equipment", [])
        e = key_or_obj if isinstance(key_or_obj, dict) else next((x for x in all_eq if x.get("key")==key_or_obj), None)
        return gear_family_table_by_obj(e) if e else "_Unknown equipment key_"

    @env.macro
    def gear_index_by_set(set_name, slot=None, include_empty=False, label_empty="(TBD)"):
        eq = env.variables.get("equipment", [])
        rows = _gear_filter(eq, slot=slot, set_name=set_name)
        if not rows:
            return "_No equipment found_"
        rows = sorted(rows, key=lambda e: (e.get("slot",""), e.get("race") or "", e.get("gender") or "", e.get("family","")))
        out = ["| Family | Slot | Race | Gender | Example Bonus (Tier +1) |","|---|---|---|---|---|"]
        for e in rows:
            tiers = e.get("tiers") or []
            if not tiers and not include_empty:
                continue
            first = tiers[0] if tiers else {}
            ex = ", ".join(first.get("bonus",{}).keys()) or label_empty
            anchor = gear_anchor_key(e)
            family_link = f"[**{_esc(e.get('family',''))}**](#{anchor})"
            out.append(f"| {family_link} | {_esc(e.get('slot',''))} | {_esc(e.get('race') or 'Any')} | {_esc(e.get('gender') or 'Any')} | {_esc(ex)} |")
        return "\n".join(out) if len(out) > 2 else "_No equipment with data yet_"

    @env.macro
    def gear_tables_by_set(set_name, slot=True, race=True, gender=True):
        eq = env.variables.get("equipment", [])
        rows = [e for e in eq if str(e.get("set","")).lower()==str(set_name).lower()]
        if not rows:
            return "_No equipment found_"
        rows = sorted(rows, key=lambda e: (e.get("slot",""), e.get("race") or "", e.get("gender") or "", e.get("family","")))
        parts = [gear_family_table_by_obj(e, slot=slot, race=race, gender=gender) for e in rows]
        return "\n\n".join(parts).strip()
