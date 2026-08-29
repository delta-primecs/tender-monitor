"""
ONE-OFF BACKFILL — fill missing `subject` on historical contract records.

Why: subject/amendment fields were added to the ingester recently, so only
records from the last ~45 days carry a subject. The 36-month history (7800+
records) has no subject, which blocks accurate title-vs-service checking.

Good news: the ΚΗΜΔΗΣ API returns `title` in the SAME window calls the
ingester already uses — no per-ΑΔΑΜ requests needed. So this backfill costs
the same ~75 window calls as a first-run, not thousands of calls.

What this does:
  • Re-scans the full 36-month window (like a first run)
  • For every ΑΔΑΜ already in the store that lacks a subject, fills in
    subject + amendment from the freshly-fetched title
  • Saves incrementally so a 429 / crash can be resumed safely

What this does NOT do:
  • Does NOT change any record's tagged `service`
  • Does NOT fire any events (no RENEWAL / NEW / etc.)
  • Does NOT delete or supersede anything
  • Does NOT add new records (only enriches existing ones)

Run:  python backfill_subjects.py
Best run from GitHub Actions (stable IP, no Aegean SSL block).
Safe to run multiple times — idempotent.
"""

import json
import os
import time

# Reuse the ingester's own logic so parsing is identical.
from ingest_contracts import (
    windows, fetch_window, parse, load_store, save_store,
    BACKFILL_MONTHS,
)

PAUSE_BETWEEN_WINDOWS = 2.0   # be polite; avoid 429
SAVE_EVERY_N_WINDOWS = 5      # checkpoint so we can resume


def main():
    store = load_store()
    if not store:
        print("Store is empty — nothing to backfill. Run the ingester first.")
        return

    # How many records currently lack a subject?
    missing_before = sum(
        1 for r in store.values()
        if not r.get("superseded_by") and not r.get("subject")
    )
    print(f"Store has {len(store)} records; {missing_before} lack a subject.")
    if missing_before == 0:
        print("Nothing to do — every record already has a subject.")
        return

    wins = windows(BACKFILL_MONTHS)
    print(f"Re-scanning {len(wins)} windows across {BACKFILL_MONTHS} months …")

    filled = 0
    seen_adams = 0
    for i, (dfrom, dto) in enumerate(wins, start=1):
        try:
            batch = fetch_window(dfrom, dto)
        except Exception as e:
            print(f"  window {i}/{len(wins)} {dfrom}->{dto}: FETCH FAILED "
                  f"({type(e).__name__}) — saving progress and stopping. "
                  f"Re-run to resume.")
            save_store(store)
            return

        window_fills = 0
        for c in batch:
            p = parse(c)
            adam = p.get("adam")
            if not adam or adam not in store:
                continue
            seen_adams += 1
            rec = store[adam]
            # Only fill if subject is currently missing and we now have one.
            if not rec.get("subject") and p.get("subject"):
                rec["subject"] = p["subject"]
                rec["amendment"] = p.get("amendment", False)
                filled += 1
                window_fills += 1

        print(f"  window {i}/{len(wins)} {dfrom}->{dto}: "
              f"{len(batch)} fetched, {window_fills} subjects filled "
              f"(running total: {filled})")

        # Checkpoint
        if i % SAVE_EVERY_N_WINDOWS == 0:
            save_store(store)
            print(f"    checkpoint saved ({filled} filled so far)")

        time.sleep(PAUSE_BETWEEN_WINDOWS)

    save_store(store)

    missing_after = sum(
        1 for r in store.values()
        if not r.get("superseded_by") and not r.get("subject")
    )
    print()
    print("=" * 70)
    print(f"BACKFILL COMPLETE")
    print(f"  Subjects filled this run:      {filled}")
    print(f"  Records still missing subject: {missing_after}")
    if missing_after:
        print(f"  (Those {missing_after} may be older than {BACKFILL_MONTHS} "
              f"months, or the API no longer returns them. That's expected.)")
    print("=" * 70)
    print("Next: run diagnose_chain.py again — now it has subjects to check.")


if __name__ == "__main__":
    main()
