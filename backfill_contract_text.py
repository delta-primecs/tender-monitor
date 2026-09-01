"""
BACKFILL full-text contract pages for the ACTIVE opportunity window.

Not all 8000 contracts — only the ones you actually look at: contracts whose
end date is in the future, OR expired within the last N days (still fresh
opportunities). Generates the readable full-text page for each so they open
instantly in the What Changed split-view.

Commits INCREMENTALLY (every batch) so a 60-min timeout never loses work —
just re-run and it resumes from where it stopped (skip-if-exists).

Run:  python backfill_contract_text.py [days_back]
Meant for GitHub Actions.
"""

import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta

from contract_reader import generate_for_adam

STORE = "data/contracts.jsonl"
PAUSE = 1.2           # seconds between PDFs — polite to ΚΗΜΔΗΣ
COMMIT_EVERY = 20     # commit+push after this many new pages


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def commit_progress(n_done):
    git("config", "user.name", "tender-bot")
    git("config", "user.email", "tender-bot@users.noreply.github.com")
    git("add", "docs/contracts/")
    staged = git("diff", "--staged", "--quiet")
    if staged.returncode == 0:
        return  # nothing new to commit
    git("commit", "-m", f"Backfill contract text (+{n_done})")
    for _ in range(3):
        pull = git("pull", "--rebase", "origin", "main")
        push = git("push")
        if pull.returncode == 0 and push.returncode == 0:
            print(f"    [committed {n_done} pages so far]")
            return
        time.sleep(6)
    print("    [commit failed this round — will retry next batch]")


def main():
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    if not os.path.exists(STORE):
        print(f"ERROR: {STORE} not found.")
        return

    cutoff = (date.today() - timedelta(days=days_back)).isoformat()

    targets, seen = [], set()
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
            adam, end = rec.get("adam"), rec.get("end")
            if not adam or adam in seen:
                continue
            if end and end >= cutoff:
                targets.append(adam)
                seen.add(adam)

    print(f"Active-window contracts (end >= {cutoff}): {len(targets)}")
    print("Generating (skipping existing, committing every "
          f"{COMMIT_EVERY}) …\n")

    ok = exists = failed = 0
    since_commit = 0
    for i, adam in enumerate(targets, start=1):
        if os.path.exists(f"docs/contracts/{adam}.html"):
            exists += 1
            continue
        res = generate_for_adam(adam, skip_if_exists=True)
        if res:
            ok += 1
            since_commit += 1
        else:
            failed += 1
        if since_commit >= COMMIT_EVERY:
            commit_progress(ok)
            since_commit = 0
        if i % 25 == 0:
            print(f"  {i}/{len(targets)} — {ok} new, {exists} existed, {failed} failed")
        time.sleep(PAUSE)

    # final commit
    if since_commit:
        commit_progress(ok)

    print()
    print("=" * 64)
    print(f"BACKFILL PASS COMPLETE — {ok} new, {exists} existed, {failed} failed")
    if failed or (ok + exists) < len(targets):
        print("Re-run to continue any remaining (resume is automatic).")
    print("=" * 64)


if __name__ == "__main__":
    main()
