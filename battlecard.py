"""
BATTLECARD GENERATOR — reads one ΑΔΑΜ, produces a sales battlecard.

Flow:
  1. Download the contract PDF from ΚΗΜΔΗΣ (same endpoint the ingester uses)
  2. Extract text — pdfplumber first, Greek OCR fallback for scanned pages
  3. Locate: Αντικείμενο, Παραδοτέα, Ποσά/Διάρκεια
  4. Compute "attack points" — audit-engagement elements the incumbent did
     NOT mention, i.e. where you can differentiate
  5. Write an HTML battlecard to docs/battlecards/<ADAM>.html (GitHub Pages)

Run (locally or via Actions):  python battlecard.py <ADAM>
Meant to run on GitHub Actions (stable IP, no 429; OCR tools installed there).
"""

import html
import os
import re
import sys
import unicodedata

import requests

CONTRACT_URL = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract"
OUT_DIR = "docs/battlecards"

SESSION = requests.Session()
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
        total=5, connect=5, read=5, backoff_factor=2.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]))))
except Exception:
    pass


def strip_accents(s):
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


# ── Download ──────────────────────────────────────────────────────────────
def download_pdf(adam, dest):
    url = f"{CONTRACT_URL}/attachment/{adam}"
    r = SESSION.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
    return dest


# ── Text extraction with OCR fallback ─────────────────────────────────────
def extract_text(pdf_path):
    import pdfplumber
    pages, ocr_pages = [], []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            if len(txt.strip()) < 40:
                ocr_pages.append(i)
                txt = ocr_page(pdf_path, i)
            pages.append(txt)
    return "\n".join(pages), ocr_pages


def ocr_page(pdf_path, page_number):
    try:
        from pdf2image import convert_from_path
        import pytesseract
        imgs = convert_from_path(pdf_path, first_page=page_number,
                                 last_page=page_number, dpi=250)
        return pytesseract.image_to_string(imgs[0], lang="ell") if imgs else ""
    except Exception as e:
        return f"[OCR failed: {type(e).__name__}]"


# ── Section heuristics ────────────────────────────────────────────────────
OBJECT_HEADINGS = [
    "αντικειμενο της συμβασης", "αντικειμενο του εργου", "αντικειμενο παροχης",
    "περιγραφη του αντικειμενου", "αντικειμενο", "σκοπος",
]
DELIVERABLE_HEADINGS = [
    "παραδοτεο φασης 1", "παραδοτεα φασης 1", "χρονοδιαγραμμα υλοποιησης",
    "παραδοτεα", "παραδοτεο", "παραδοτεα υπηρεσιας", "παραδοτεα εργου",
    "εκθεσεις",
]
STOP_HEADINGS = [
    "διαρκεια", "αμοιβη", "προϋπολογισμος", "τιμημα", "πληρωμη",
    "τροπος πληρωμης", "λοιποι οροι", "αρθρο 2", "αρθρο 3",
    "εγγυησεις", "ποινικες ρητρες", "μερικο συνολο",
]


def find_section(full_text, starts, stops, max_chars=3000):
    flat = strip_accents(full_text.lower())
    start_idx, matched = None, None
    for h in starts:
        idx = flat.find(h)
        if idx != -1 and (start_idx is None or idx < start_idx):
            start_idx, matched = idx, h
    if start_idx is None:
        return None
    sec_start = start_idx + len(matched)
    rest = flat[sec_start:]
    stops_found = [rest.find(h) for h in stops if rest.find(h) != -1]
    stop_idx = min(stops_found) if stops_found else min(len(rest), max_chars)
    stop_idx = min(stop_idx, max_chars)
    return full_text[sec_start:sec_start + stop_idx].strip()


def deliverable_bullets(text):
    if not text:
        return []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    bullets, i = [], 0
    while i < len(lines):
        flat = strip_accents(lines[i].lower())
        is_title = (re.match(r"^παραδοτ", flat) or re.match(r"^φαση\s*\d", flat)
                    or re.match(r"^π\.?\d", flat) or re.match(r"^[0-9]+[\.\)]\s", flat))
        if is_title:
            title = lines[i]
            parts, j = [], i + 1
            while j < len(lines) and j <= i + 2:
                nxt = strip_accents(lines[j].lower())
                if re.match(r"^παραδοτ|^φαση\s*\d|^π\.?\d", nxt):
                    break
                parts.append(lines[j]); j += 1
            bullets.append(title + (" — " + " ".join(parts) if parts else ""))
            i = j
        else:
            i += 1
    return bullets


# ── Attack points ─────────────────────────────────────────────────────────
# Elements a STRONG internal-audit engagement includes. If the incumbent's
# contract doesn't mention one, that's a differentiation angle for you.
ATTACK_CHECKS = [
    ("Ετήσιο Πρόγραμμα Ελέγχου", ["ετησιο προγραμμα", "προγραμμα ελεγχου"]),
    ("Έκθεση με Γνώμη", ["γνωμη", "εκθεση με γνωμη"]),
    ("Διαχείριση Κινδύνων / Μητρώο Κινδύνων", ["κινδυν", "μητρωο κινδ"]),
    ("Follow-up συστάσεων", ["παρακολουθηση", "follow", "συστασ", "επανελεγχ"]),
    ("Εγχειρίδιο / Κανονισμός ΜΕΕ", ["εγχειριδιο", "κανονισμος", "μεε"]),
    ("Εκπαίδευση προσωπικού", ["εκπαιδευσ", "καταρτισ προσωπικ", "training"]),
    ("Χαρτογράφηση διαδικασιών", ["χαρτογραφ", "διαδικασ"]),
    ("Πιστοποίηση / εξειδίκευση ομάδας", ["πιστοποιησ", "cia", "cisa", "acca"]),
    ("Help Desk / συνεχής υποστήριξη", ["help desk", "συνεχης", "υποστηριξ"]),
    ("Συμμόρφωση (whistleblowing / ΓΚΠΔ)", ["whistleblow", "καταγγελ", "γκπδ", "4990"]),
]


def attack_points(full_text):
    flat = strip_accents(full_text.lower())
    present, missing = [], []
    for label, kws in ATTACK_CHECKS:
        if any(k in flat for k in kws):
            present.append(label)
        else:
            missing.append(label)
    return present, missing


# ── HTML output ───────────────────────────────────────────────────────────
def build_html(adam, obj, bullets, deliv_raw, euros, months, present, missing, ocr_pages):
    def esc(x): return html.escape(x or "")
    bullets_html = "".join(f"<li>{esc(b)}</li>" for b in bullets) if bullets else \
        f"<p class='muted'>Δεν εντοπίστηκαν διακριτά παραδοτέα. Ακατέργαστο κείμενο:</p><pre>{esc((deliv_raw or '')[:1500])}</pre>"
    present_html = "".join(f"<li class='has'>{esc(p)}</li>" for p in present) or "<li class='muted'>—</li>"
    missing_html = "".join(f"<li class='gap'>{esc(m)}</li>" for m in missing) or "<li class='muted'>—</li>"
    euros_html = ", ".join(esc(e) for e in euros[:10]) or "—"
    months_html = ", ".join(esc(m) for m in months[:6]) or "—"
    ocr_note = (f"<p class='muted'>OCR χρησιμοποιήθηκε στις σελίδες: {ocr_pages}</p>"
                if ocr_pages else "")

    return f"""<!doctype html>
<html lang="el"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Battlecard — {esc(adam)}</title>
<style>
  body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
       max-width:820px;margin:0 auto;padding:24px;color:#1a2233;line-height:1.5}}
  h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:15px;margin:26px 0 8px;
     border-bottom:2px solid #012267;padding-bottom:4px;color:#012267}}
  .adam{{font-family:monospace;color:#51565c;font-size:13px}}
  .muted{{color:#8a93a2}} pre{{white-space:pre-wrap;background:#f6f8fa;
     padding:10px;border-radius:6px;font-size:12px}}
  ul{{margin:6px 0;padding-left:20px}} li{{margin:3px 0;font-size:14px}}
  li.has{{color:#1a7a4c}} li.gap{{color:#b23b2e;font-weight:600}}
  .box{{background:#f6f8fa;border:1px solid #e2e7ee;border-radius:8px;padding:12px 16px}}
  .attack{{background:#fdf6f5;border-color:#f0d5d0}}
  .row{{display:flex;gap:16px;flex-wrap:wrap}} .row>div{{flex:1;min-width:220px}}
</style></head><body>
<h1>Battlecard</h1>
<div class="adam">ΑΔΑΜ: {esc(adam)}</div>
{ocr_note}

<h2>Αντικείμενο — τι ανέλαβε ο ανάδοχος</h2>
<div class="box">{esc(obj) if obj else "<span class='muted'>Δεν εντοπίστηκε καθαρά — χειροκίνητος έλεγχος.</span>"}</div>

<h2>Παραδοτέα — τι υποσχέθηκε να παραδώσει</h2>
<ul>{bullets_html}</ul>

<h2>Ποσά & Διάρκεια</h2>
<div class="box">Ποσά: {euros_html}<br>Διάρκειες (μήνες): {months_html}</div>

<h2>Σημεία επίθεσης — πού να διαφοροποιηθείς</h2>
<div class="row">
  <div class="box">
    <b>✓ Τι ΚΑΛΥΠΤΕΙ ήδη</b>
    <ul>{present_html}</ul>
  </div>
  <div class="box attack">
    <b>✗ Τι ΛΕΙΠΕΙ (η ευκαιρία σου)</b>
    <ul>{missing_html}</ul>
  </div>
</div>
<p class="muted" style="margin-top:20px">⚠ Αυτόματη ανάλυση — επιβεβαίωσε πάντα με το πρωτότυπο PDF πριν την κλήση.</p>
</body></html>"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python battlecard.py <ADAM>")
        sys.exit(1)
    adam = sys.argv[1].strip()
    os.makedirs(OUT_DIR, exist_ok=True)
    pdf_path = f"/tmp/{adam}.pdf"

    print(f"Downloading {adam} …")
    try:
        download_pdf(adam, pdf_path)
    except Exception as e:
        print(f"Download failed: {type(e).__name__}: {e}")
        sys.exit(1)

    print("Extracting text …")
    full_text, ocr_pages = extract_text(pdf_path)
    print(f"  chars: {len(full_text)}, OCR pages: {ocr_pages}")

    obj = find_section(full_text, OBJECT_HEADINGS, STOP_HEADINGS, 1200)
    deliv_raw = find_section(full_text, DELIVERABLE_HEADINGS, STOP_HEADINGS, 3000)
    bullets = deliverable_bullets(deliv_raw)
    euros = list(dict.fromkeys(re.findall(r"[\d\.]+,\d{2}\s*€|\€\s*[\d\.]+,\d{2}", full_text)))
    months = list(dict.fromkeys(re.findall(r"\b(\d{1,2})\s*(?:\(\d{1,2}\)\s*)?μην", strip_accents(full_text.lower()))))
    present, missing = attack_points(full_text)

    out_html = build_html(adam, obj, bullets, deliv_raw, euros, months,
                          present, missing, ocr_pages)
    out_path = f"{OUT_DIR}/{adam}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"\nBattlecard written: {out_path}")
    print(f"View at: https://delta-primecs.github.io/tender-monitor/battlecards/{adam}.html")
    # Console summary too
    print("\n--- SUMMARY ---")
    print(f"Αντικείμενο: {(obj or '(none)')[:160]}")
    print(f"Παραδοτέα: {len(bullets)} εντοπίστηκαν")
    print(f"Καλύπτει: {', '.join(present) or '—'}")
    print(f"ΛΕΙΠΕΙ:   {', '.join(missing) or '—'}")


if __name__ == "__main__":
    main()
