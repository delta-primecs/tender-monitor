"""
Diagnose subject-vs-service tagging quality in the existing contract store.

Reads data/contracts.jsonl and, for every non-superseded record, tests three
signals against what the ingester tagged as the service:

  1. Umbrella CPV        — the CPV used is too generic to trust alone
  2. Subject-positive    — subject has words that CONFIRM the tagged service
  3. Subject-negative    — subject has words that CONTRADICT the tagged service

Then classifies each record:

  CLEAN            — positive signal present, no problem
  UMBRELLA_ONLY    — umbrella CPV, no positive signal   → yellow badge candidate
  AMBIGUOUS        — no positive signal, no negative     → orange badge candidate
  MISMATCH         — negative signal detected            → red badge candidate

Prints counts and up to 10 real examples per category so you can eyeball the
noise level. NO writes to the store — pure diagnostic.

Run:  python diagnose_chain.py
Paste the output back and we design the fix on real evidence.
"""

import json
import os
import re
from collections import Counter, defaultdict

STORE = "data/contracts.jsonl"

# Umbrella CPVs — too generic to be a single-source signal.
UMBRELLA_CPVS = {
    "79200000-6",   # Business services generally
    "79411000-8",   # Management consulting generally
    "79220000-2",   # Financial services generally
    "72221000-0",   # Business analysis consulting
    "71700000-5",   # Monitoring & control services
    "79212400-7",   # Risk management (broad; can be non-audit risk)
}

POSITIVE_KEYWORDS = {
    "Εσωτερικός έλεγχος": [
        "εσωτερικ", "ενδογεν", "δικλίδ", "δικλειδ", "μεε ", " μεε",
        "μονάδα ελέγχου", "μοναδα ελεγχου", "μονάδας ελέγχου",
        "ν.4795", "ν. 4795", "4795/2021", "4795/21",
        "internal audit", "internal control",
    ],
    "Διαχείριση κινδύνων": [
        "κινδύν", "κινδυν", "μητρώο κινδ", "μητρωο κινδ",
        "ν.5013", "ν. 5013", "5013/2023", "5013/23",
        "risk management", "risk assessment",
        "διαχείριση κιν", "διαχειριση κιν",
    ],
    "Χαρτογράφηση / Οργάνωση": [
        "χαρτογράφ", "χαρτογραφ", "διαδικασ",
        "οργανωτικ", "οργάνωσ", "οργανωσ",
        "καταγραφή διαδ", "καταγραφη διαδ",
    ],
    "Οικονομικός έλεγχος / Ορκωτοί": [
        "οικονομικ έλεγχ", "οικονομικ ελεγχ",
        "ορκωτ", "χρηματοοικονομικ έλεγχ",
        "financial audit", "statutory audit",
        "ελεγκτικές υπηρεσίες", "ελεγκτικες υπηρεσιες",
    ],
    "DPO / Προστασία δεδομένων": [
        "dpo", "προστασία δεδομ", "προστασια δεδομ",
        "γκπδ", "gdpr", "προστασ προσωπικ",
    ],
    "Συμμόρφωση / Whistleblowing": [
        "συμμόρφωσ", "συμμορφωσ", "καταγγελ", "whistleblow",
        "ν.4990", "ν. 4990", "4990/2022",
        "δίαυλοι", "διαυλοι",
    ],
    "Λογιστικές υπηρεσίες": [
        "λογιστ", "τήρηση βιβλί", "τηρηση βιβλι",
        "λογιστήρι", "λογιστηρι",
    ],
    "Φορολογικές υπηρεσίες": [
        "φορολογ", "φπα", "φ.π.α", "τax", "μισθοδοσ",
    ],
    "Επιχειρηματική / οικονομική συμβουλευτική": [
        "επιχειρηματικ σχ", "στρατηγικ", "επιχειρησιακ σχ",
        "business plan", "financial advis",
    ],
}

NEGATIVE_KEYWORDS = [
    # IT / software
    "λογισμικ", "software", "hardware", "εφαρμογ πληροφορικ",
    "πληροφοριακό σύστημα", "πληροφοριακο συστημα",
    "development", "ανάπτυξ λογισμικ",
    # Facilities / cleaning / maintenance
    "καθαρισμ", "καθαριστ", "συντήρησ κτιρι", "συντηρησ κτιρι",
    "συντήρησ εξοπλισμ", "συντηρησ εξοπλισμ",
    # Vehicles / transport
    "οχήματ", "οχηματ", "μεταφορ", "καύσιμ", "καυσιμ",
    # Medical / clinical / surgical
    "χειρουργεί", "χειρουργει", "ιατρικ", "νοσηλευτικ",
    "φαρμακ", "εμβολιασμ",
    # Construction / civil works
    "κατασκευ", "ανακαίν", "ανακαιν", "οδοποιί", "οδοποιι",
    # Marketing / events
    "διαφήμισ", "διαφημισ", "εκδήλωσ", "εκδηλωσ",
]


def normalize(text):
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"\s+", " ", t)
    return t


def has_positive(subject, service):
    kws = POSITIVE_KEYWORDS.get(service, [])
    s = normalize(subject)
    return any(kw in s for kw in kws)


def has_negative(subject):
    s = normalize(subject)
    for kw in NEGATIVE_KEYWORDS:
        if kw in s:
            return kw
    return None


def get_cpvs_from_record(rec):
    v = rec.get("cpv") or rec.get("cpvs") or []
    if isinstance(v, str):
        return [v]
    return list(v)


def main():
    if not os.path.exists(STORE):
        print(f"ERROR: {STORE} not found. Run this script from the repo root.")
        return

    total = 0
    by_service = Counter()
    classify_counts = Counter()
    examples = defaultdict(list)
    missing_subject = 0
    superseded = 0

    with open(STORE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            if rec.get("superseded_by"):
                superseded += 1
                continue

            service = rec.get("service")
            if not service:
                continue

            total += 1
            by_service[service] += 1

            subject = rec.get("subject") or ""
            if not subject:
                missing_subject += 1

            cpvs = get_cpvs_from_record(rec)
            has_umbrella = any(c in UMBRELLA_CPVS for c in cpvs)
            positive = has_positive(subject, service)
            negative_kw = has_negative(subject)

            if negative_kw:
                category = "MISMATCH"
            elif positive:
                category = "CLEAN"
            elif has_umbrella:
                category = "UMBRELLA_ONLY"
            else:
                category = "AMBIGUOUS"

            classify_counts[category] += 1

            if len(examples[category]) < 10:
                examples[category].append({
                    "adam": rec.get("adam"),
                    "org": (rec.get("org") or "")[:60],
                    "holder": (rec.get("holder") or "")[:50],
                    "service": service,
                    "subject": subject[:120] if subject else "(no subject)",
                    "cpvs": cpvs[:3],
                    "negative_hit": negative_kw,
                })

    print("=" * 78)
    print(f"CONTRACT STORE DIAGNOSTIC")
    print("=" * 78)
    print(f"  Total non-superseded records: {total}")
    print(f"  Superseded (skipped):         {superseded}")
    print(f"  Records missing 'subject':    {missing_subject}"
          f"  ({100*missing_subject//max(total,1)}%)")
    print()
    print("Records by tagged service:")
    for svc, n in by_service.most_common():
        print(f"  {n:>5}  {svc}")
    print()
    print("-" * 78)
    print("CLASSIFICATION (this is the noise level)")
    print("-" * 78)
    for cat in ("CLEAN", "UMBRELLA_ONLY", "AMBIGUOUS", "MISMATCH"):
        n = classify_counts[cat]
        pct = 100 * n // max(total, 1)
        bar = "#" * (pct // 2)
        print(f"  {cat:<15} {n:>5}  ({pct:>3}%)  {bar}")
    print()

    for cat in ("MISMATCH", "AMBIGUOUS", "UMBRELLA_ONLY", "CLEAN"):
        exs = examples[cat]
        if not exs:
            continue
        print("-" * 78)
        print(f"EXAMPLES -- {cat}  ({classify_counts[cat]} total, showing up to 10)")
        print("-" * 78)
        for ex in exs:
            print(f"  ADAM: {ex['adam']}")
            print(f"    tagged as: {ex['service']}")
            print(f"    org:       {ex['org']}")
            print(f"    holder:    {ex['holder']}")
            print(f"    CPVs:      {', '.join(ex['cpvs']) if ex['cpvs'] else '(none stored)'}")
            print(f"    subject:   {ex['subject']}")
            if ex["negative_hit"]:
                print(f"    !! negative keyword hit: {ex['negative_hit']!r}")
            print()

    print("=" * 78)
    print("Paste this whole output back. Two things to focus on:")
    print("  1. What % is MISMATCH  -> false-positive events (real noise)")
    print("  2. What % is AMBIGUOUS -> need better subject or manual verify")


if __name__ == "__main__":
    main()
