# LOOMSHIELD — STRATEGIC PRODUCT ROADMAP & ARCHITECTURAL SKETCHES

This document outlines the post-Round 3 development roadmap and architectural design sketches for capabilities declared in Round 3 for future implementation.

---

## 1. STRATEGIC ROADMAP OVERVIEW

LoomShield's product roadmap focuses on deepening compliance coverage, scaling enterprise document throughput, and enhancing team collaboration:

| Phase | Milestone | Focus Areas | Target Release |
| :--- | :--- | :--- | :--- |
| **Phase 1** | *Shipped (Round 3)* | Guideline Clarity Rewriter, Visual Heatmap Inspector, Ed25519 Compliance Certificates (v2), Separation of Duties, Hash Routing. | v2.2.0 (Shipped) |
| **Phase 2** | *Enterprise Scale* | 100 MB Streaming Uploads, Brand Vault Import/Export, Extended File Formats (EPUB, PPTX). | v2.3.0 |
| **Phase 3** | *Collaboration* | Threaded Inline Comments, Multi-Reviewer Approval Chains, Webhook Notifications. | v2.4.0 |
| **Phase 4** | *Ecosystem* | Pre-built Brand Presets, Figma & Canva MCP Sidecar Integrations, CMS Publishing Connectors. | v3.0.0 |

---

## 2. ARCHITECTURAL DESIGN SKETCHES FOR DECLARED CAPABILITIES

### 2.1 Capability 1: Presets for Existing Brands
- **Rationale for Declaration:** Pre-seeding commercial brand guidelines (e.g., Apple, Stripe, NHS) carries trademark sensitivity and liability risks if proprietary rules become outdated. Declarative presets will be provided via an extensible schema rather than hardcoded proprietary profiles.
- **Data Model:**
  ```json
  {
    "preset_schema_version": 1,
    "brand_id": "preset_fintech_standard",
    "name": "Fintech Transparency Standard",
    "industry": "Financial Technology",
    "tone_principles": "Calm, precise, transparent about fees and settlement timelines.",
    "colors": [
      { "name": "Deep Slate", "hex_code": "#0F172A", "role": "primary" },
      { "name": "Emerald Clear", "hex_code": "#10B981", "role": "accent" }
    ],
    "rules": [
      { "pillar": "Promotional Claims", "title": "Guaranteed Returns Prohibition", "severity": "high" }
    ],
    "terminology": [
      { "term": "instant", "category": "prohibited", "replacement": "real-time settlement" }
    ]
  }
  ```
- **UX Flow:** A preset gallery in the Brand Vault provides searchable templates with one-click cloning into isolated workspace organizations.

### 2.2 Capability 2: 100 MB Streaming Uploads
- **Rationale for Declaration:** Single-tenant and serverless cloud instances with strict memory constraints require a streaming pipeline. The current 5 MB chunked limit prevents resource starvation while covering 99% of marketing copy and vector banners.
- **Streaming Pipeline Architecture:**
  ```python
  # ASGI Chunked Stream Handler with Disk Spooling
  async def stream_upload_handler(request: Request, max_size_bytes: int = 104_857_600):
      spooled = tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024)  # 4 MB RAM buffer
      bytes_read = 0
      async for chunk in request.stream():
          bytes_read += len(chunk)
          if bytes_read > max_size_bytes:
              spooled.close()
              raise HTTPException(status_code=413, detail="Payload exceeds 100 MB streaming limit.")
          spooled.write(chunk)
      spooled.seek(0)
      return spooled
  ```
- **Memory Footprint:** Keeps resident set size (RSS) strictly bounded under 15 MB regardless of file size.

### 2.3 Capability 3: Inline Comments & Collaborative Review
- **Rationale for Declaration:** Structured finding-level decisions (`accept`, `modify`, `dismiss` with mandatory justifications) currently solve the governance requirement. Threaded conversational text comments add UI complexity without strengthening the audit log.
- **Database Schema Sketch:**
  ```sql
  CREATE TABLE IF NOT EXISTS audit_inline_comments (
      id TEXT PRIMARY KEY,
      audit_id TEXT NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
      finding_id TEXT REFERENCES findings(id) ON DELETE SET NULL,
      author_user_id TEXT NOT NULL,
      char_start INTEGER NOT NULL,
      char_end INTEGER NOT NULL,
      comment_text TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open', -- 'open', 'resolved'
      created_at TEXT NOT NULL,
      resolved_at TEXT,
      FOREIGN KEY(audit_id) REFERENCES audits(id)
  );
  ```
- **UI Integration:** Canvas annotation overlay anchored to document character spans in the Three-Panel workspace with keyboard navigation (`C` to comment).

### 2.4 Capability 4: Brand Vault Import and Export
- **Rationale for Declaration:** Direct REST API endpoints with idempotent migrations provide complete management capabilities. Bulk file import requires schema version negotiation and namespace deduplication to prevent accidental guideline overrides.
- **Archive Format:** `.loomshield-vault.json` bundling brand metadata, rules, terminology, verified facts, and approved logo assets with an Ed25519 signature of the archive manifest:
  ```json
  {
    "loomshield_archive_version": 2,
    "brand": { "id": "novapay", "version": 4 },
    "manifest_sha256": "4a7f...",
    "signature_b64": "..."
  }
  ```
- **Validation Pipeline:** Dry-run schema validation, foreign key integrity cross-check, conflict resolution modal (Overwrite vs Duplicate as New Brand).
