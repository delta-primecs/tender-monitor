"""
CONTRACT READER — the full contract text, clean, in your browser.

You wanted "the contract without having the contract" — so this extracts the
COMPLETE text (OCR fallback for scanned pages), cleans it up, splits it into
readable sections by article/heading, and renders it in the Gödel terminal
style. Nothing is dropped — every line of the source is preserved.

Flow:
  1. Download PDF from ΚΗΜΔΗΣ
  2. Extract all text (pdfplumber + Greek OCR fallback)
  3. Clean (fix hyphenation, collapse noise, keep everything)
  4. Detect section boundaries (ΑΡΘΡΟ, ΑΝΤΙΚΕΙΜΕΝΟ, ΠΑΡΑΔΟΤΕΑ, etc.)
  5. Render full HTML to docs/contracts/<ADAM>.html

Run:  python contract_reader.py <ADAM>
Meant for GitHub Actions (stable IP, OCR installed there).
"""

import html
import os
import re
import sys

import requests

CONTRACT_URL = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract"
OUT_DIR = "docs/contracts"

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


def download_pdf(adam, dest):
    url = f"{CONTRACT_URL}/attachment/{adam}"
    r = SESSION.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
    return dest


def extract_text(pdf_path):
    """Extract every page. OCR any page that looks scanned. Returns list of
    (page_number, text, was_ocr)."""
    import pdfplumber
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            was_ocr = False
            if len(txt.strip()) < 40:
                txt = ocr_page(pdf_path, i)
                was_ocr = True
            out.append((i, txt, was_ocr))
    return out


def ocr_page(pdf_path, page_number):
    try:
        from pdf2image import convert_from_path
        import pytesseract
        imgs = convert_from_path(pdf_path, first_page=page_number,
                                 last_page=page_number, dpi=300)
        return pytesseract.image_to_string(imgs[0], lang="ell") if imgs else ""
    except Exception as e:
        return f"[OCR απέτυχε: {type(e).__name__}]"


def clean_text(text):
    """Light cleaning that preserves everything:
    - join words split by hyphen at line end (κιν-\ndύνων → κινδύνων)
    - collapse 3+ blank lines to 2
    - strip trailing spaces
    Does NOT remove content."""
    # de-hyphenate line breaks
    text = re.sub(r"([α-ωά-ώa-z])-\n([α-ωά-ώa-z])", r"\1\2", text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    # collapse excess blank lines
    cleaned, blanks = [], 0
    for ln in lines:
        if not ln.strip():
            blanks += 1
            if blanks <= 1:
                cleaned.append("")
        else:
            blanks = 0
            cleaned.append(ln)
    return "\n".join(cleaned).strip()


# Section headings we try to detect as boundaries (for nicer reading).
# If none match, the whole text is shown as one block — nothing is lost.
SECTION_PATTERNS = [
    (r"^\s*ΑΡΘΡΟ\s+\d+\b.*$", "article"),
    (r"^\s*ΆΡΘΡΟ\s+\d+\b.*$", "article"),
    (r"^\s*Άρθρο\s+\d+\b.*$", "article"),
    (r"^\s*ΑΝΤΙΚΕΙΜΕΝΟ\b.*$", "heading"),
    (r"^\s*ΠΑΡΑΔΟΤΕ[ΑΟ]\b.*$", "heading"),
    (r"^\s*ΔΙΑΡΚΕΙΑ\b.*$", "heading"),
    (r"^\s*ΑΜΟΙΒΗ\b.*$", "heading"),
    (r"^\s*ΠΡΟΫΠΟΛΟΓΙΣΜΟΣ\b.*$", "heading"),
    (r"^\s*ΤΡΟΠΟΣ ΠΛΗΡΩΜΗΣ\b.*$", "heading"),
    (r"^\s*ΥΠΟΧΡΕΩΣΕΙΣ\b.*$", "heading"),
    (r"^\s*ΧΡΟΝΟΔΙΑΓΡΑΜΜΑ\b.*$", "heading"),
    (r"^\s*ΕΓΓΥΗΣΕΙΣ\b.*$", "heading"),
]


def split_sections(text):
    """Split into (heading, body) blocks by detected boundaries.
    Everything before the first heading becomes an intro block."""
    lines = text.splitlines()
    boundaries = []
    for idx, ln in enumerate(lines):
        for pat, kind in SECTION_PATTERNS:
            if re.match(pat, ln):
                boundaries.append((idx, ln.strip(), kind))
                break
    if not boundaries:
        return [("", text)]
    sections = []
    # intro before first boundary
    first = boundaries[0][0]
    if first > 0:
        intro = "\n".join(lines[:first]).strip()
        if intro:
            sections.append(("", intro))
    for b in range(len(boundaries)):
        start = boundaries[b][0]
        end = boundaries[b + 1][0] if b + 1 < len(boundaries) else len(lines)
        heading = boundaries[b][1]
        body = "\n".join(lines[start + 1:end]).strip()
        sections.append((heading, body))
    return sections


def build_html(adam, sections, ocr_pages, total_chars):
    def esc(x): return html.escape(x or "")
    blocks = ""
    for heading, body in sections:
        body_html = esc(body).replace("\n", "<br>")
        if heading:
            blocks += f'<section><h2>{esc(heading)}</h2><div class="txt">{body_html}</div></section>'
        else:
            blocks += f'<section><div class="txt">{body_html}</div></section>'
    ocr_note = (f'<span class="tag ocr">OCR: σελ. {ocr_pages}</span>' if ocr_pages else "")
    khmdhs = f"{CONTRACT_URL}/attachment/{esc(adam)}"

    return f"""<!doctype html>
<html lang="el"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Σύμβαση {esc(adam)}</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root{{
    --page:#0a0e14;--panel:#0f141c;--text:#d4dae3;--bright:#f0f4f9;
    --muted:#5f6e82;--hair:#1c2530;--hair2:#26313f;--accent:#3ddc84;
    --amber:#e8a13a;--link:#5db0ff;--mono:'JetBrains Mono',ui-monospace,Menlo,monospace;
  }}
  *{{box-sizing:border-box}}html,body{{margin:0}}
  body{{background:var(--page);color:var(--text);font-family:var(--mono);
       font-size:13px;line-height:1.6;padding:16px 14px 60px}}
  .wrap{{max-width:840px;margin:0 auto}}
  .bar{{background:var(--panel);border:1px solid var(--hair);padding:12px 16px;
       display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:2px}}
  .bar .t{{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);
       font-weight:700}}
  .adam{{color:var(--bright);font-weight:700;font-size:14px}}
  .tag{{font-size:10px;padding:2px 8px;border:1px solid var(--hair2);color:var(--muted);
       text-transform:uppercase;letter-spacing:.05em}}
  .tag.ocr{{color:var(--amber);border-color:#4a3a17;background:#2a2010}}
  .src{{margin-left:auto;color:var(--link);text-decoration:none;font-size:11px}}
  .src:hover{{text-decoration:underline}}
  section{{background:var(--panel);border:1px solid var(--hair);border-top:0;padding:0}}
  h2{{margin:0;padding:10px 16px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;
     color:var(--accent);background:#0c1219;border-bottom:1px solid var(--hair);
     position:sticky;top:0}}
  .txt{{padding:14px 16px;white-space:normal;color:var(--text);font-size:13px}}
  .txt br{{content:"";display:block;margin:2px 0}}
  .foot{{color:var(--muted);font-size:11px;margin-top:14px;padding:0 4px;line-height:1.6}}
  .foot b{{color:var(--text)}}
</style></head><body><div class="wrap">
  <div class="bar">
    <span class="t">Σύμβαση</span>
    <span class="adam">{esc(adam)}</span>
    {ocr_note}
    <a class="src" href="{khmdhs}" target="_blank" rel="noopener">Πρωτότυπο PDF ↗</a>
  </div>
  {blocks}
  <div class="foot">
    <b>{total_chars}</b> χαρακτήρες εξήχθησαν · Πλήρες κείμενο, χωρίς περικοπές.<br>
    ⚠ Αυτόματη εξαγωγή (+ OCR όπου χρειάστηκε) — για νομική βεβαιότητα δες το πρωτότυπο PDF.
  </div>
</div></body></html>"""


def generate_for_adam(adam, skip_if_exists=True):
    """Download + extract + render the full-text page for one ΑΔΑΜ.
    Returns True if a page now exists, False on failure. Safe to call from
    the ingester or a backfill loop."""
    adam = adam.strip()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = f"{OUT_DIR}/{adam}.html"
    if skip_if_exists and os.path.exists(out_path):
        return True
    pdf_path = f"/tmp/{adam}.pdf"
    try:
        download_pdf(adam, pdf_path)
    except Exception as e:
        print(f"  [{adam}] download failed: {type(e).__name__}")
        return False
    try:
        pages = extract_text(pdf_path)
        ocr_pages = [p for p, _, was in pages if was]
        raw = "\n".join(t for _, t, _ in pages)
        cleaned = clean_text(raw)
        sections = split_sections(cleaned)
        out_html = build_html(adam, sections, ocr_pages, len(cleaned))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_html)
        return True
    except Exception as e:
        print(f"  [{adam}] extract failed: {type(e).__name__}")
        return False
    finally:
        try:
            os.remove(pdf_path)
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print("Usage: python contract_reader.py <ADAM>")
        sys.exit(1)
    adam = sys.argv[1].strip()
    print(f"Generating full text for {adam} …")
    ok = generate_for_adam(adam, skip_if_exists=False)
    if ok:
        print(f"Written: {OUT_DIR}/{adam}.html")
        print(f"View: https://delta-primecs.github.io/tender-monitor/contracts/{adam}.html")
    else:
        print("Failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
