"""Mark republished duplicates in data/contracts.jsonl.

ΚΗΜΔΗΣ often republishes the same contract under a new ΑΔΑΜ (corrections,
re-uploads), with the contractor name spelled slightly differently. Two live
records are treated as the same contract only when ALL of these match:
same organisation, same signing date, same subject (normalised), same
contractor (normalised first 8 letters) and same value (rounded to €1).
Different contractors on the same day = separate lots, so they are kept.

The record with the most filled fields (then the lowest ΑΔΑΜ) is kept; the
others get superseded_by=<kept adam> and dup=True, which every builder
already excludes.
"""
import json, re, collections, unicodedata

PATH = "data/contracts.jsonl"
FIELDS = ("subject", "end", "holder", "signer", "region", "value")


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\W", "", s)


def key(r):
    try:
        v = round(float(r.get("value") or 0))
    except (TypeError, ValueError):
        v = 0
    return (str(r.get("orgkey")), r.get("signed"), norm(r.get("subject"))[:60],
            norm(r.get("holder"))[:8], v)


def main():
    recs = [json.loads(l) for l in open(PATH, encoding="utf-8") if l.strip()]
    groups = collections.defaultdict(list)
    for r in recs:
        if r.get("superseded_by") or not r.get("subject") or not r.get("signed"):
            continue
        groups[key(r)].append(r)
    marked = 0
    for g in groups.values():
        if len(g) < 2:
            continue
        g.sort(key=lambda r: (-sum(1 for f in FIELDS if r.get(f)), r["adam"]))
        keep = g[0]
        for r in g[1:]:
            r["superseded_by"] = keep["adam"]
            r["dup"] = True
            marked += 1
    with open(PATH, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    live = sum(1 for r in recs if not r.get("superseded_by"))
    print(f"Dedupe: marked {marked} republications · live records {live}/{len(recs)}")


if __name__ == "__main__":
    main()
