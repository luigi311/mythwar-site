# macros/pets.py
from html import escape as _escape

# ---------- helpers ----------

def _to_str(x, default=""):
    return "" if x is None else str(x)

def _esc(x):
    """Escape safely even when x is None/number/etc."""
    return _escape(_to_str(x))



def _val_or_zero(x): 
    try: 
        return int(x)
    except Exception:
        try:
            return float(x) if x is not None else 0
        except Exception:
            return 0

def _range_or_single(dct, key):
    """
    dct: e.g. pet['statRates']
    key: 'sta' | 'int' | 'str' | 'agi' | 'growthRate'
    returns (display_text, min_val, max_val)
    """
    sub = (dct or {}).get(key, {})
    mn = sub.get("min")
    mx = sub.get("max")
    if mn is None and mx is None:
        return ("—", None, None)
    if mn == mx:
        # show single; prefer int if it's whole
        v = float(mn)
        v = int(v) if abs(v - int(v)) < 1e-9 else v
        return (str(v), mn, mx)
    # show range; try to format tightly
    def fmt(v):
        f = float(v)
        return str(int(f)) if abs(f - int(f)) < 1e-9 else f"{f:g}"
    return (f"{fmt(mn)}–{fmt(mx)}", mn, mx)

def _stars_from_build(build, key, empty="—"):
    """
    key: 'sta' | 'int' | 'str' | 'agi'
    Uses build[key] as number of stars (1..4).
    """
    n = _val_or_zero((build or {}).get(key))
    if n <= 0:
        return empty
    return "★" * int(n)

def _fmt_list(val):
    if not val:
        return "—"
    if isinstance(val, str):
        return "**" + _esc(val) + "**"
    # be defensive: stringify and skip None items
    return "<hr>".join("**" + _esc(x) + "**" for x in (val or []) if x is not None)

def _kv_block(d):
    if not d: return "—"
    return "<br>".join(f"{_esc(k)} **{_esc(v)}**" for k, v in d.items())

# ---------- register ----------

def register(env, store):
    @env.macro
    def pet_row(pet):
        # Basics (nil-safe)
        name = _esc(pet.get("name", ""))
        img  = _to_str(pet.get("image", ""))  # don't escape yet (used in src='')
        species = _esc(pet.get("species", ""))

        # Only render <img> when url is truthy after stripping
        img_html = f" <img src='{_esc(img)}'/>" if img.strip() else ""

        # Skills & Sources
        skills  = _fmt_list(pet.get("skills"))
        sources = _fmt_list(pet.get("sources"))

        # Stat blocks
        sr = pet.get("statRates") or {}
        build = pet.get("build") or {}

        def _range_or_single(dct, key):
            sub = (dct or {}).get(key, {})
            mn = sub.get("min")
            mx = sub.get("max")
            if mn is None and mx is None:
                return ("—", None, None)
            if mn == mx:
                v = float(mn)
                v = int(v) if abs(v - int(v)) < 1e-9 else v
                return (str(v), mn, mx)
            def fmt(v):
                f = float(v)
                return str(int(f)) if abs(f - int(f)) < 1e-9 else f"{f:g}"
            return (f"{fmt(mn)}–{fmt(mx)}", mn, mx)

        def _val_or_zero(x):
            try:
                return int(x)
            except Exception:
                try:
                    return int(float(x))  # coerce floats like "5.0" to 5
                except Exception:
                    return 0

        def _stars_from_build(bld, key, empty="—"):
            n = _val_or_zero((bld or {}).get(key))
            if n <= 0:
                return "☆"  # show hollow star when 0/None
            return "★" * int(n)

        growth_txt, _, _ = _range_or_single(sr, "growthRate")

        def _one_stat(label, key):
            txt, _, _ = _range_or_single(sr, key)
            stars = _stars_from_build(build, key)
            return f"{label}: **{_esc(txt)}** <br>{stars}"

        stats_block = "<hr>".join([
            _one_stat("Sta", "sta"),
            _one_stat("Int", "int"),
            _one_stat("Str", "str"),
            _one_stat("Agi", "agi"),
        ])

        # --- Resist blocks (unchanged logic, now using _esc/_to_str internally) ---
        def _physical(resist):
            r = resist or {}
            def v(x, d=0): 
                try: return int(x)
                except Exception:
                    try: return int(float(x))
                    except Exception: return d
            pierce_rate   = v(r.get("pierce"))
            pierce_dmg    = v(r.get("pierceDamage"))
            crit_rate     = v(r.get("criticalRate"))
            crit_dmg      = v(r.get("criticalDamage"))
            combo_rate    = v(r.get("comboRate"))
            combo_hit     = v(r.get("comboHit"))
            hit           = v(r.get("hit", 100))
            dodge         = v(r.get("dodgeRate", 0))
            defense       = v(r.get("defense", 0))
            melee_resist  = v(r.get("meleeResist", 0))
            counter       = v(r.get("counter", 0))
            melee_reflect = v(r.get("meleeReflect", 0))
            rows = [
                ("Hit",             f"{hit}"),
                ("Dodge",           f"{dodge}"),
                ("Defense",         f"{defense}"),
                ("Melee",           f"{melee_resist}"),
                ("Pierce",          f"{pierce_rate}% ({pierce_dmg})"),
                ("Berserk",         "0% (0)"),
                ("Critical",        f"{crit_rate}% ({crit_dmg})"),
                ("Combo",           f"{combo_rate}% ({combo_hit})"),
                ("Counter",         f"0% ({counter})" if counter else "0% (0)"),
                ("Melee reflect",   f"0% ({melee_reflect})" if melee_reflect else "0% (0)"),
            ]
            return "<br>".join(f"{k} **{_esc(v)}**" for k, v in rows)

        def _magical(resist):
            r = resist or {}
            def v(key): 
                try: return int(r.get(key, 0))
                except Exception:
                    try: return int(float(r.get(key, 0)))
                    except Exception: return 0
            rows = [
                ("Evil",           f"{v('evilResist')}"),
                ("Flash",          f"{v('flashResist')}"),
                ("Ice",            f"{v('iceResist')}"),
                ("Fire",           f"{v('fireResist')}"),
                ("Drain",          f"{v('drainResist')}"),
                ("Magic reflect",  "0% (0)"),
            ]
            return "<br>".join(f"{k} **{_esc(v)}**" for k, v in rows)

        def _elemental(resist):
            r = resist or {}
            def v(key): 
                try: return int(r.get(key, 0))
                except Exception:
                    try: return int(float(r.get(key, 0)))
                    except Exception: return 0
            rows = [
                ("Death",      f"{v('deathResist')}"),
                ("Poison",     f"{v('poisonResist')}"),
                ("Chaos",      f"{v('chaosResist')}"),
                ("Stun",       f"{v('stunResist')}"),
                ("Hypnotize",  f"{v('hypnotizeResist')}"),
                ("Frailty",    f"{v('frailtyResist')}"),
            ]
            return "<br>".join(f"{k} **{_esc(v)}**" for k, v in rows)

        resist = pet.get("resist") or {}
        physical   = _physical(resist)
        magical    = _magical(resist)
        elemental  = _elemental(resist)

        # Final row
        row = (
            f"| **{name}**{img_html} "
            f"| {species} "
            f"| **{_esc(growth_txt)}** "
            f"| {skills} "
            f"| {stats_block} "
            f"| {sources} "
            f"| {physical} "
            f"| {magical} "
            f"| {elemental} |"
        )
        return row.strip()

    # add to register() in macros/pets.py
    @env.macro
    def pets_table(pet_keys=None):
        """
        Optional convenience: render the header + rows for all pets or a subset.
        Usage:
        {{ pets_table() }}
        {{ pets_table(["bee","aquarius"]) }}
        """
        all_pets = env.variables.get("pets", [])
        rows = all_pets if not pet_keys else [p for p in all_pets if str(p.get("key")) in set(map(str, pet_keys))]
        header = "| Pet | Species | Growth | Skills | Stats | Sources | Physical | Magical | Elemental |\n|---|---|---|---|---|---|---|---|---|"
        body = "\n".join(pet_row(p) for p in rows)
        return header + "\n" + (body or "_No pets_")

