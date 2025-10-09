from html import escape

def _fmt_price(p):
    if p in (None, ""): return "—"
    try: return f"{int(p):,} gold"
    except Exception: return escape(str(p))

def _fmt_source(src):
    if not src: return "—"
    if isinstance(src, (list, tuple)):
        return "<br>".join(escape(str(s)) for s in src)
    return escape(str(src))

def register(env, store):
    @env.macro
    def consumable_row(consumable):
        name = escape(consumable.get("name", ""))
        price = _fmt_price(consumable.get("price"))
        desc = escape(consumable.get("description", ""))
        src = _fmt_source(consumable.get("source"))
        return f"| **{name}** | {price} | {desc} | {src} |"

    @env.macro
    def consumables_table(category=None, sort_by="name"):
        its = env.variables.get("consumables", []) or []
        if category:
            its = [i for i in its
                   if str(i.get("category","")).lower() == str(category).lower()]

        def _key(i):
            v = i.get(sort_by)
            return "" if v is None else str(v)

        its = sorted(its, key=_key)
        if not its:
            return "_No consumables yet_"
        header = "| Item | Price | Description | Source |\n|---|---:|---|---|"
        rows = [consumable_row(i) for i in its]
        return "\n".join([header, *rows])
