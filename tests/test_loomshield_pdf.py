import io
import os
import sys
import pytest
import pypdf
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import init_db, reset_demo_workspace
from backend.engine import parse_uploaded_file, run_six_pillar_audit, get_engine_status
from backend.main import app

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_clean_db():
    init_db()
    reset_demo_workspace()
    yield
    reset_demo_workspace()


def build_pdf_bytes(page_texts: list) -> bytes:
    """Helper to synthesize standard in-memory test PDFs without external dependencies."""
    writer = pypdf.PdfWriter()
    for text in page_texts:
        # Sanitize text for simple PostScript string literal
        safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_bytes = f"BT /F1 12 Tf 72 712 Td ({safe_text}) Tj ET".encode("latin1", errors="replace")
        length = len(stream_bytes)
        raw_page = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
            + f"4 0 obj<</Length {length}>>stream\n".encode("latin1")
            + stream_bytes
            + b"\nendstream\nendobj\n"
            b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            b"xref\n0 6\n0000000000 65535 f \n"
            b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n500\n%%EOF\n"
        )
        r = pypdf.PdfReader(io.BytesIO(raw_page))
        writer.add_page(r.pages[0])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def build_multiparagraph_pdf_bytes(pages: list) -> bytes:
    """Helper to create pages with multiple paragraphs separated by newlines."""
    writer = pypdf.PdfWriter()
    for paragraphs in pages:
        # paragraphs is a list of paragraph strings
        commands = []
        y_pos = 712
        for p in paragraphs:
            safe_text = p.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"BT /F1 12 Tf 72 {y_pos} Td ({safe_text}) Tj ET")
            y_pos -= 50
        stream_bytes = "\n".join(commands).encode("latin1", errors="replace")
        length = len(stream_bytes)
        raw_page = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
            + f"4 0 obj<</Length {length}>>stream\n".encode("latin1")
            + stream_bytes
            + b"\nendstream\nendobj\n"
            b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            b"xref\n0 6\n0000000000 65535 f \n"
            b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n500\n%%EOF\n"
        )
        r = pypdf.PdfReader(io.BytesIO(raw_page))
        writer.add_page(r.pages[0])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ============================================================================
# 1. NORMAL TEXT-BASED PDF & ENGINE STATUS
# ============================================================================

def test_pdf_format_in_engine_status():
    status = get_engine_status()
    assert "pdf" in status["supported_input_formats"]
    assert "pdf" in status["supported_formats"]
    limitation_text = " ".join(status["honest_limitations"])
    assert "Local PDF processing" in limitation_text
    assert "OCR" in limitation_text


def test_pdf_normal_single_page_extraction():
    raw_pdf = build_pdf_bytes(["NovaPay provides institutional cross-border treasury settlement."])
    parsed = parse_uploaded_file("report.pdf", raw_pdf)
    assert parsed["parse_ok"] is True
    assert parsed["input_format"] == "pdf"
    assert "NovaPay provides institutional cross-border treasury settlement." in parsed["extracted_text"]
    assert parsed["page_count"] == 1
    assert len(parsed["page_spans"]) == 1
    assert parsed["page_spans"][0]["page"] == 1
    assert parsed["error"] is None


# ============================================================================
# 2. MULTIPAGE PDF PROCESSING
# ============================================================================

def test_pdf_multipage_text_extraction_and_spans():
    p1 = "Page 1: NovaPay platform overview and executive summary."
    p2 = "Page 2: Cross-border settlement network details."
    p3 = "Page 3: Compliance and regional regulatory frameworks."
    raw_pdf = build_pdf_bytes([p1, p2, p3])

    parsed = parse_uploaded_file("multipage.pdf", raw_pdf)
    assert parsed["parse_ok"] is True
    assert parsed["page_count"] == 3
    assert len(parsed["page_spans"]) == 3
    for idx, span in enumerate(parsed["page_spans"], start=1):
        assert span["page"] == idx
        assert span["end"] >= span["start"]

    assert p1 in parsed["extracted_text"]
    assert p2 in parsed["extracted_text"]
    assert p3 in parsed["extracted_text"]


# ============================================================================
# 3. SCANNED / EMPTY PDF DETECTION (NO SELECTABLE TEXT)
# ============================================================================

def test_pdf_scanned_or_empty_no_selectable_text():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    blank_pdf = buf.getvalue()

    parsed = parse_uploaded_file("scanned_document.pdf", blank_pdf)
    assert parsed["parse_ok"] is False
    assert parsed["input_format"] == "pdf"
    assert parsed["extracted_text"] == ""
    assert "no usable selectable text" in parsed["error"].lower()
    assert "ocr" in parsed["error"].lower()

    # When audited via API, it must NOT be marked compliant
    files = {"file": ("scanned_document.pdf", blank_pdf, "application/pdf")}
    data = {"brand_id": "novapay", "document_name": "Scanned Agreement"}
    res = client.post("/api/audits/upload", files=files, data=data)
    assert res.status_code == 200
    res_data = res.json()
    # All pillar states must be 'Check Failed'
    assert all(state == "Check Failed" for state in res_data["pillar_states"].values())
    # Must have a high-severity finding explaining the lack of OCR
    findings = res_data["findings"]
    assert any("OCR" in f["explanation"] or "selectable text" in f["explanation"] for f in findings)


# ============================================================================
# 4. PASSWORD-PROTECTED / ENCRYPTED PDF
# ============================================================================

def test_pdf_password_protected_encrypted_handling():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt(user_password="StrictPassword123!")
    buf = io.BytesIO()
    writer.write(buf)
    encrypted_pdf = buf.getvalue()

    parsed = parse_uploaded_file("confidential_locked.pdf", encrypted_pdf)
    assert parsed["parse_ok"] is False
    assert "password-protected or encrypted" in parsed["error"].lower()

    files = {"file": ("confidential_locked.pdf", encrypted_pdf, "application/pdf")}
    res = client.post("/api/audits/upload", files=files, data={"brand_id": "novapay"})
    assert res.status_code == 200
    res_data = res.json()
    assert all(state == "Check Failed" for state in res_data["pillar_states"].values())
    assert any("encrypted" in f["explanation"].lower() for f in res_data["findings"])


# ============================================================================
# 5. CORRUPTED OR MALFORMED PDF
# ============================================================================

def test_pdf_corrupted_structure_handling():
    corrupted_pdf = b"%PDF-1.4\n1 0 obj <</Invalid>>\x00\xff\xfe truncated stream EOF"
    parsed = parse_uploaded_file("damaged.pdf", corrupted_pdf)
    assert parsed["parse_ok"] is False
    assert "could not be parsed" in parsed["error"].lower() or "malformed" in parsed["error"].lower()


# ============================================================================
# 6. NON-PDF FILE RENAMED TO .PDF (MAGIC BYTE VALIDATION)
# ============================================================================

def test_pdf_magic_bytes_validation_non_pdf_renamed():
    fake_pdf = b"Hello, I am a plain text file pretending to be a PDF."
    parsed = parse_uploaded_file("renamed_text.pdf", fake_pdf)
    assert parsed["parse_ok"] is False
    assert "signature" in parsed["error"].lower() or "%pdf-" in parsed["error"].lower()


def test_pdf_empty_0_bytes():
    parsed = parse_uploaded_file("empty.pdf", b"")
    assert parsed["parse_ok"] is False
    assert "empty" in parsed["error"].lower()


# ============================================================================
# 7. PAGE LIMIT ENFORCEMENT (LOOMSHIELD_MAX_PDF_PAGES)
# ============================================================================

def test_pdf_page_limit_enforced(monkeypatch):
    monkeypatch.setenv("LOOMSHIELD_MAX_PDF_PAGES", "3")
    pages = [f"Page {i} text" for i in range(1, 6)]
    pdf_5_pages = build_pdf_bytes(pages)

    parsed = parse_uploaded_file("large_document.pdf", pdf_5_pages)
    assert parsed["parse_ok"] is False
    assert "maximum page limit of 3 pages" in parsed["error"]
    assert "document has 5 pages" in parsed["error"]


# ============================================================================
# 8. 5 MB FILE SIZE LIMIT
# ============================================================================

def test_pdf_oversized_5mb_upload_rejected():
    big_dummy = b"%PDF-1.4\n" + (b"0" * (5 * 1024 * 1024 + 100))
    files = {"file": ("too_large.pdf", big_dummy, "application/pdf")}
    res = client.post("/api/audits/upload", files=files, data={"brand_id": "novapay"})
    assert res.status_code == 400
    assert "5 MB" in res.json()["detail"]


# ============================================================================
# 9. TERMINOLOGY & PROMOTIONAL CLAIM DETECTION ON PDF TEXT
# ============================================================================

def test_pdf_auditing_detects_terminology_and_claim_violations():
    # NovaPay Brand Vault:
    # Prohibited: 'unhackable' (TERM-03)
    # Claim Fact 101: Settlement is 'up to 64% faster'
    # Violation: 'guarantees 95% faster processing'
    pdf_text = (
        "NovaPay is the leader in modern finance.\n\n"
        "Our platform guarantees 95% faster processing for cross-border settlement. "
        "We also offer unhackable security for all treasury accounts."
    )
    raw_pdf = build_pdf_bytes([pdf_text])

    files = {"file": ("novapay_announcement.pdf", raw_pdf, "application/pdf")}
    res = client.post("/api/audits/upload", files=files, data={"brand_id": "novapay"})
    assert res.status_code == 200
    data = res.json()

    # Verify input_format is pdf
    assert data["input_format"] == "pdf"
    assert "unhackable" in data["original_content"]

    findings = data["findings"]
    term_findings = [f for f in findings if f["pillar"] == "Terminology"]
    claim_findings = [f for f in findings if f["pillar"] == "Promotional Claims"]

    assert len(term_findings) >= 1
    assert any("unhackable" in f["flagged_text"].lower() for f in term_findings)

    assert len(claim_findings) >= 1
    assert any("95%" in f["flagged_text"] for f in claim_findings)


# ============================================================================
# 10. PAGE-NUMBER AND PARAGRAPH MAPPING
# ============================================================================

def test_pdf_page_number_and_paragraph_mapping():
    # Page 1: 2 paragraphs. Paragraph 2 has a terminology issue ('blitz-scale').
    # Page 2: 1 paragraph with an exaggerated claim ('guarantees 95% faster processing').
    page1_p1 = "Welcome to NovaPay treasury solutions."
    page1_p2 = "We help your finance team blitz-scale across regions."

    page2_p1 = "Our core settlement engine guarantees 95% faster processing across regions."

    raw_pdf = build_pdf_bytes([
        f"{page1_p1}\n\n{page1_p2}",
        page2_p1,
    ])

    files = {"file": ("mapped_spec.pdf", raw_pdf, "application/pdf")}
    res = client.post("/api/audits/upload", files=files, data={"brand_id": "novapay"})
    assert res.status_code == 200
    data = res.json()

    findings = data["findings"]
    # Check that findings reference Page 1 and Page 2
    para_refs = [f.get("paragraph_ref", "") for f in findings]
    has_page_1 = any("Page 1, P2" in r for r in para_refs)
    has_page_2 = any("Page 2, P1" in r for r in para_refs)
    assert has_page_1, f"Expected a finding mapped to 'Page 1, P2', got refs: {para_refs}"
    assert has_page_2, f"Expected a finding mapped to 'Page 2, P1', got refs: {para_refs}"


# ============================================================================
# 11. HONEST REPORTING OF VISUAL CHECKS FOR TEXT-BASED PDF
# ============================================================================

def test_pdf_visual_checks_honestly_reported_not_checked():
    raw_pdf = build_pdf_bytes(["Standard corporate guidelines without colors or raster images."])
    files = {"file": ("plain_text.pdf", raw_pdf, "application/pdf")}
    res = client.post("/api/audits/upload", files=files, data={"brand_id": "novapay"})
    assert res.status_code == 200
    data = res.json()

    pillar_states = data["pillar_states"]
    # Visual and Logo Consistency MUST NOT be marked Passed for a text-based PDF without visual specs
    assert pillar_states["Visual and Logo Consistency"] == "Not Checked"


# ============================================================================
# 12. REGRESSION TESTING FOR EXISTING FORMATS (DOCX, MD, HTML, TXT, SVG, PNG)
# ============================================================================

def test_regression_existing_formats_still_work():
    # 1. Plain Text
    res_txt = client.post(
        "/api/audits/upload",
        files={"file": ("memo.txt", b"NovaPay provides safe treasury.", "text/plain")},
        data={"brand_id": "novapay"},
    )
    assert res_txt.status_code == 200
    assert res_txt.json()["input_format"] == "txt"

    # 2. Markdown
    res_md = client.post(
        "/api/audits/upload",
        files={"file": ("memo.md", b"# NovaPay Header\n\nContent here.", "text/markdown")},
        data={"brand_id": "novapay"},
    )
    assert res_md.status_code == 200
    assert res_md.json()["input_format"] == "md"

    # 3. HTML
    res_html = client.post(
        "/api/audits/upload",
        files={"file": ("memo.html", b"<h1>NovaPay</h1><p>Content.</p>", "text/html")},
        data={"brand_id": "novapay"},
    )
    assert res_html.status_code == 200
    assert res_html.json()["input_format"] == "html"

    # 4. SVG
    svg_data = b'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><title>Logo</title><text>NovaPay</text></svg>'
    res_svg = client.post(
        "/api/audits/upload",
        files={"file": ("logo.svg", svg_data, "image/svg+xml")},
        data={"brand_id": "novapay"},
    )
    assert res_svg.status_code == 200
    assert res_svg.json()["input_format"] == "svg"


# ============================================================================
# 13. ZERO EXTERNAL NETWORK CALLS DURING PDF PROCESSING
# ============================================================================

def test_pdf_local_processing_zero_external_network(monkeypatch):
    import socket

    def forbidden_connect(*args, **kwargs):
        raise RuntimeError("External network connection attempted during local PDF processing!")

    monkeypatch.setattr(socket, "create_connection", forbidden_connect)

    raw_pdf = build_pdf_bytes(["Confidential internal document processed completely locally."])
    parsed = parse_uploaded_file("confidential.pdf", raw_pdf)
    assert parsed["parse_ok"] is True
    assert "Confidential internal document" in parsed["extracted_text"]
