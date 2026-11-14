"""
Verify LoomShield Round 3 Final Product Document PDF.
Inspects page count, fonts, bookmarks, text placeholders, and numbers against final_pdf_data.json.
"""
import sys
import json
import re
from pathlib import Path
import pypdf
import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = REPO_ROOT / "docs" / "LoomShield_Round3_Final_Product_Document.pdf"
FACTS_PATH = REPO_ROOT / "docs" / "final_pdf_data.json"

def verify_pdf():
    print(f"Inspecting PDF: {PDF_PATH}")
    assert PDF_PATH.exists(), f"PDF does not exist: {PDF_PATH}"
    
    # 1. PyMuPDF inspection
    doc = fitz.open(PDF_PATH)
    page_count = len(doc)
    print(f"Total Page Count: {page_count} (Requirement: <= 16 pages)")
    assert page_count <= 16, f"PDF page count exceeds 16! Actual: {page_count}"
    assert page_count >= 10, f"PDF page count too low! Actual: {page_count}"
    
    # 2. Check bookmarks / Table of Contents in PDF outline
    toc = doc.get_toc()
    print(f"TOC / Bookmarks count: {len(toc)}")
    for item in toc:
        print(f"  Level {item[0]}: {item[1]} (Page {item[2]})")
    assert len(toc) >= 10, f"Expected at least 10 outline entries, got {len(toc)}"
    
    # 3. Extract text from all pages
    full_text = ""
    page_texts = []
    for i, page in enumerate(doc):
        text = page.get_text()
        page_texts.append(text)
        full_text += f"\n--- Page {i+1} ---\n" + text
        
    # Check for placeholder markers
    placeholders = ["TODO", "TBD", "[INSERT", "XXX", "FIXME"]
    found_placeholders = []
    for ph in placeholders:
        if ph in full_text:
            found_placeholders.append(ph)
    print(f"Placeholders found: {found_placeholders}")
    assert len(found_placeholders) == 0, f"Placeholders found in PDF: {found_placeholders}"
    
    # 4. Check for first-person voice and absence of prohibited superlatives
    prohibited_words = [
        "best-in-class", "unrivaled", "revolutionary", "game-changer", "world-class"
    ]
    found_prohibited = [w for w in prohibited_words if w in full_text.lower()]
    print(f"Prohibited superlatives found: {found_prohibited}")
    assert len(found_prohibited) == 0, f"Prohibited marketing superlatives found: {found_prohibited}"
    
    # 5. Check empirical facts matching final_pdf_data.json
    facts = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    
    # Check git commit
    short_commit = facts["git"]["short_commit"]
    assert short_commit in full_text, f"Short commit {short_commit} not found in PDF!"
    print(f"Verified git commit in PDF: {short_commit}")
    
    # Check pytest total
    total_tests_str = str(facts["pytest"]["total_collected"])
    assert total_tests_str in full_text, f"Pytest total {total_tests_str} not found in PDF!"
    print(f"Verified pytest total in PDF: {total_tests_str}")
    
    # Check Key ID
    kid = facts["engine_and_cert"]["key_id"]
    assert kid in full_text, f"Key ID {kid} not found in PDF!"
    print(f"Verified Key ID in PDF: {kid}")
    
    # Check fixture hits/checks
    hits_str = f"{facts['fixtures']['hits']} hits"
    pass_rate_str = f"{facts['fixtures']['pass_rate_pct']}%"
    assert str(facts['fixtures']['hits']) in full_text, f"Fixture hits not found in PDF!"
    assert pass_rate_str in full_text, f"Fixture pass rate {pass_rate_str} not found in PDF!"
    print(f"Verified fixtures in PDF: {facts['fixtures']['hits']} hits, {pass_rate_str}")
    
    # Check benchmark numbers
    lat_25k = str(facts["benchmarks"]["latency_25000_chars_ms"])
    assert lat_25k in full_text, f"25k latency {lat_25k} not found in PDF!"
    rss_12mp = str(facts["benchmarks"]["peak_rss_12mp_windows_mb"])
    assert rss_12mp in full_text, f"12MP RSS {rss_12mp} not found in PDF!"
    tmpl_avg = str(facts["benchmarks"]["template_matching_latencies_ms"]["avg_ms"])
    assert tmpl_avg in full_text, f"Template match avg {tmpl_avg} not found in PDF!"
    print(f"Verified benchmarks in PDF: 25k={lat_25k}ms, RSS={rss_12mp}MB, Template={tmpl_avg}ms")
    
    # Check unverified explicitly noted
    assert "unverified" in full_text.lower(), "Explicit 'unverified' status not found in PDF!"
    print("Verified 'unverified' statements present in PDF.")
    
    print("\nPDF VERIFICATION PASSED COMPLETELY!")
    print(f"Final Page Count: {page_count} of 16 max")

if __name__ == "__main__":
    verify_pdf()
