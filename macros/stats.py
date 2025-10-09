import math, statistics

def _to_number(x):
    if isinstance(x, (int, float)): return int(x)
    if isinstance(x, str):
        try: return int(float(x.strip()))
        except Exception: return None
    return None

def _collect_values(pets, stat_name):
    vals = []
    for p in pets or []:
        v = (p.get("stats") or {}).get(stat_name)
        v = _to_number(v)
        if v is not None:
            vals.append(v)
    return vals

def _derive_thresholds(values):
    if not values: return None
    values = sorted(values)
    uniq = sorted(set(values))
    vmax = uniq[-1]
    if len(uniq) == 1:
        v = uniq[0]
        return [v, v, v, v]
    try:
        q1, q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
        t1 = int(math.floor(q1))
        t2 = max(t1, int(math.floor(q2)))
        t3 = max(t2, int(math.floor(q3)))
        t4 = vmax
        return [t1, t2, t3, t4]
    except Exception:
        vmin = values[0]; span = max(1, vmax - vmin)
        return [vmin + span // 4, vmin + span // 2, vmin + (3*span)//4, vmax]

def _build_thresholds(pets, overrides=None, stats=("Sta","Int","Str","Agi")):
    overrides = overrides or {}
    thresholds = {}
    for name in stats:
        if overrides.get(name):
            thresholds[name] = overrides[name]
        else:
            vals = _collect_values(pets, name)
            t = _derive_thresholds(vals)
            if t: thresholds[name] = t
    return thresholds

def register(env, store):
    overrides = {
        # "Sta": [60, 100, 130, 140],
        # "Int": [60, 80, 100, 120],
        # ...
    }
    thresholds = _build_thresholds(store.get("pets", []), overrides)
    env.variables["stat_thresholds"] = thresholds

    def starify(value, stat_name=None, default_thresholds=(20,50,100,140)):
        v = _to_number(value)
        if v is None: return str(value)
        ts = thresholds.get(stat_name, default_thresholds)
        stars = sum(1 for t in ts if v >= t)
        return "☆" if stars == 0 else "★"*stars

    # Make starify available to other modules & templates
    env.variables["starify"] = starify
