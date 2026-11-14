"""Frozen ordered D1/D2 matcher used for deployment evaluation."""
def match(name, normalized, d1, d2):
    if name in d1["raw"]:
        return {"source": "D1", "matchType": "raw", "entry": name, **d1["raw"][name]}
    if normalized in d1["normalized"]:
        return {"source": "D1", "matchType": "normalized", "entry": normalized, **d1["normalized"][normalized]}
    if name in d2["exact"]:
        return {"source": "D2", "matchType": "exact", "entry": name, **d2["exact"][name]}
    candidates = [(len(prefix), prefix, item) for prefix, item in d2["wildcard"].items() if name.startswith(prefix)]
    if not candidates:
        return None
    longest = max(item[0] for item in candidates)
    best = [item for item in candidates if item[0] == longest]
    if len({item[2]["label"] for item in best}) != 1:
        return None
    _, prefix, item = sorted(best, key=lambda item: item[1])[0]
    return {"source": "D2", "matchType": "wildcard", "entry": prefix, **item}
