"""
BACKFILL full-text contract pages for the ACTIVE opportunity window.

Not all 8000 contracts — only the ones you actually look at: contracts whose
end date is in the future, OR expired within the last 90 days (still fresh
opportunities). Generates the readable full-text page for each so they open
instantly in the What Changed split-view.

Throttled (rate-limit friendly), skips pages that already exist (resume-safe).

Run:  python backfill_contract_text.py [days_back]
  days_back = how many days past expiry still counts as "active" (default 90)
Meant for GitHub Actions.
"""

import json
import os
import sys
import time
from datetime import date, timedelta

from contract_reader import generate_for_adam

STORE = "data/contracts.jsonl"
PAUSE = 1.5          # seconds between PDFs — polite to ΚΗΜΔΗΣ
SAVE_PING = 25       # progress print frequency


def main():
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    if not os.path.exists(STORE):
        print(f"ERROR: {STORE} not found.")
        return

    today = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()

    # Collect ΑΔΑΜs in the active window
    targets = []
    seen = set()
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
                continue
            adam = rec.get("adam")
            end = rec.get("end")
            if not adam or adam in seen:
                continue
            # active = ends in the future, or expired within days_back
            if end and end >= cutoff:
                targets.append(adam)
                seen.add(adam)

    print(f"Active-window contracts (end >= {cutoff}): {len(targets)}")
    print(f"Generating full-text pages (skipping existing) …\n")

    ok = exists = failed = 0
    for i, adam in enumerate(targets, start=1):
        out_path = f"docs/contracts/{adam}.html"
        if os.path.exists(out_path):
            exists += 1
            continue
        res = generate_for_adam(adam, skip_if_exists=True)
        if res:
            ok += 1
        else:
            failed += 1
        if i % SAVE_PING == 0:
            print(f"  {i}/{len(targets)} — {ok} new, {exists} existed, {failed} failed")
        time.sleep(PAUSE)

    print()
    print("=" * 64)
    print(f"BACKFILL COMPLETE")
    print(f"  New pages generated: {ok}")
    print(f"  Already existed:     {exists}")
    print(f"  Failed:              {failed}")
    print("=" * 64)


if __name__ == "__main__":
    main()
