"""N1 lookup: exact, normalized majority, then pinned OCD exact/prefix."""
from collections import Counter, defaultdict
import csv
from common import CREDENTIAL, label, normalize_name

def build_lookup(records, ocd):
    votes = {"raw": defaultdict(Counter), "normalized": defaultdict(Counter)}
    for row in records:
        if CREDENTIAL.search(row["name"]):
            continue
        votes["raw"][row["name"]][label(row)] += 1
        votes["normalized"][normalize_name(row["name"])][label(row)] += 1
    output = {"raw": [], "normalized": [], "ocdExact": [], "ocdPrefix": [], "droppedTies": {}}
    for kind in votes:
        ties = 0
        for name, counts in sorted(votes[kind].items()):
            if counts[0] == counts[1]:
                ties += 1
            else:
                output[kind].append({"name": name, "label": int(counts[1] > counts[0]),
                                     "trackerVotes": counts[1], "notTrackerVotes": counts[0]})
        output["droppedTies"][kind] = ties
    source = {"ocdExact": defaultdict(set), "ocdPrefix": defaultdict(set)}
    mapping = {"marketing": 1, "analytics": 1, "functional": 0, "security": 0, "personalization": 0}
    with open(ocd, newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            name = row.get("Cookie / Data Key name", "")
            category = row.get("Category", "").strip().lower()
            if not name or category not in mapping or CREDENTIAL.search(name):
                continue
            kind = "ocdPrefix" if row.get("Wildcard match", "").strip() == "1" else "ocdExact"
            source[kind][name].add(mapping[category])
    for kind in source:
        output[kind] = [{"name": n, "label": next(iter(labels))} for n, labels in sorted(source[kind].items()) if len(labels) == 1]
    return output

class Lookup:
    def __init__(self, payload):
        self.raw = {r["name"]: r for r in payload["raw"]}
        self.normalized = {r["name"]: r for r in payload["normalized"]}
        self.exact = {r["name"]: r for r in payload["ocdExact"]}
        self.prefix = sorted(payload["ocdPrefix"], key=lambda x: (-len(x["name"]), x["name"]))

    def match(self, name):
        for source, table, query in [("raw", self.raw, name), ("normalized", self.normalized, normalize_name(name)), ("ocdExact", self.exact, name)]:
            if query in table:
                return source, table[query]
        for row in self.prefix:
            if name.startswith(row["name"]):
                return "ocdPrefix", row
        return None
