"""
API PROBE — runs inside GitHub Actions (which can reach the Greek gov APIs)
and prints what the public APIs actually accept/return, so data fixes are
based on facts, not guesses. Output goes to the Actions log only.

Run:  python tools/probe.py
"""
import json
import requests

KH = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata"
DV = "https://diavgeia.gov.gr/luminapi/opendata"
S = requests.Session()
S.headers.update({"Accept": "application/json"})
samples = json.load(open("tools/probe_samples.json"))


def show(title, obj, n=1500):
    print("\n" + "=" * 8, title, "=" * 8)
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)[:n]
    print(s[:n])


def get(url, **kw):
    try:
        r = S.get(url, timeout=40, **kw)
        return r.status_code, r
    except Exception as e:
        return "ERR", str(e)


def post(url, body):
    try:
        r = S.post(url, json=body, timeout=60)
        return r.status_code, r
    except Exception as e:
        return "ERR", str(e)


# 1) ΚΗΜΔΗΣ OpenAPI spec — what does /contract accept?
for path in ["/v3/api-docs", "/v2/api-docs", "/api-docs", "/openapi.json", "/v3/api-docs/swagger-config"]:
    st, r = get(KH + path)
    print(f"spec {path}: {st}")
    if st == 200:
        try:
            spec = r.json()
        except Exception:
            show("spec (not json)", r.text[:500]); continue
        paths = spec.get("paths", {})
        show("ΚΗΜΔΗΣ endpoints", {p: list(v.keys()) for p, v in paths.items()}, 4000)
        comps = (spec.get("components") or {}).get("schemas") or spec.get("definitions") or {}
        for name, sch in comps.items():
            if any(k in name.lower() for k in ("search", "criteria", "filter", "request", "query")):
                show("schema " + name, list((sch.get("properties") or {}).keys()), 2000)
        for p, v in paths.items():
            if "contract" in p.lower():
                for m, op in v.items():
                    show(f"{m.upper()} {p} params", [x.get("name") for x in op.get("parameters", [])] +
                         [json.dumps(op.get("requestBody", {}).get("content", {}), ensure_ascii=False)[:600]], 1500)
        break

# 2) records lacking subject/end — what does ΚΗΜΔΗΣ return for them?
for adam in samples["miss_subj"][:3] + samples["miss_end"][:2]:
    for label, call in [
        ("GET /contract/{adam}", lambda a: get(f"{KH}/contract/{a}")),
        ("POST /contract referenceNumber", lambda a: post(f"{KH}/contract?page=0", {"referenceNumber": a})),
    ]:
        st, r = call(adam)
        if st == 200:
            try:
                d = r.json()
            except Exception:
                show(f"{label} {adam}", r.text[:300]); continue
            item = (d.get("content") or [d])[0] if isinstance(d, dict) else d
            keep = {k: item.get(k) for k in ("referenceNumber", "title", "subject", "endDate", "noEndDate",
                                             "contractDuration", "contractDurationUnitOfMeasure",
                                             "contractSignedDate") if isinstance(item, dict)}
            show(f"{label} {adam} ({'hits='+str(len(d.get('content',[]))) if isinstance(d,dict) and 'content' in d else ''})", keep, 800)
        else:
            print(f"{label} {adam}: {st}")

# 3) does /contract accept a TITLE filter? (finds contracts filed under a wrong CPV)
base = {"dateFrom": "2025-01-01", "dateTo": "2025-03-31"}
st, r = post(f"{KH}/contract?page=0", base)
tot0 = r.json().get("totalElements") if st == 200 else st
print(f"\nwindow, no filter: totalElements={tot0}")
for key in ("title", "keyword", "searchText", "freeText", "subject", "q"):
    st, r = post(f"{KH}/contract?page=0", {**base, key: "εσωτερικού ελέγχου"})
    if st == 200:
        d = r.json()
        titles = [c.get("title", "")[:80] for c in d.get("content", [])[:3]]
        print(f"  {key!r}: totalElements={d.get('totalElements')}  sample={titles}")
    else:
        print(f"  {key!r}: HTTP {st}")

# 4) Διαύγεια as a second source: subject search syntax
for q in ['subject:"εσωτερικού ελέγχου"', 'subject:(εσωτερικού AND ελέγχου)',
          '"εσωτερικού ελέγχου"', 'subject:"εσωτερικού ελέγχου" AND organizationUid:"6324"']:
    st, r = get(f"{DV}/search/advanced", params={"q": q, "size": 3, "page": 0, "sort": "recent"})
    if st == 200:
        d = r.json()
        info = d.get("info", {})
        subs = [x.get("subject", "")[:70] for x in (d.get("decisions") or [])[:3]]
        print(f"DIAV {q!r}: total={info.get('total')} sample={subs}")
    else:
        body = r.text[:150] if hasattr(r, "text") else r
        print(f"DIAV {q!r}: HTTP {st} {body}")
print("\nPROBE DONE")
