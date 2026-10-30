# LOOMSHIELD — STRATEGIC PRODUCT ROADMAP & ARCHITECTURAL SKETCHES

This document outlines the post-Round 3 development roadmap and architectural design sketches for capabilities declared for future implementation.

---

## 1. STRATEGIC ROADMAP OVERVIEW

LoomShield's future development focuses on production identity, enterprise scale, advanced computer vision, and cryptographic governance:

| Phase | Milestone | Focus Areas | Target Release |
| :--- | :--- | :--- | :--- |
| **Phase 1** | *Shipped (Round 3)* | Guideline Clarity Rewriter, Visual Heatmap Inspector, Ed25519 Compliance Certificates (v2), Separation of Duties, URL Hash Routing. | v2.2.0 (Shipped) |
| **Phase 2** | *Enterprise Infrastructure* | Production Identity (`docs/auth-plan.md`), Hosted Database (PostgreSQL / Managed SQLite), Per-Visitor Isolated Workspaces. | v2.3.0 |
| **Phase 3** | *Extended Ingestion & Vision* | 100 MB Streaming Uploads, Optical Character Recognition (OCR), Extended Formats (EPUB, PPTX). | v2.4.0 |
| **Phase 4** | *Governance & Key Lifecycle* | Threaded Inline Comments, Brand Vault Import/Export, Evaluation Dashboard, Certificate Key Rotation & External Timestamping. | v2.5.0 |
| **Phase 5** | *Ecosystem* | Declarative Brand Presets, Sidecar Integrations (Figma, Canva), CMS Publishing Webhooks. | v3.0.0 |

---

## 2. DESIGN NOTES FOR UNFINISHED ROUND 1 CAPABILITIES

The following four capabilities were proposed in earlier planning documents but were not finished in the time available. Below are concise design notes outlining their technical implementation:

### 2.1 Presets for Existing Brands
- **Status:** I did not finish this feature in the time available.
- **Design Note:** Rather than hardcoding proprietary company rules into source code, presets will be loaded via a declarative JSON schema. Users can import templates representing industry baselines (e.g., Fintech Transparency, Clinical Healthcare) into isolated brand profiles:
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

### 2.2 100 MB Streaming Uploads
- **Status:** I did not finish this feature in the time available. The current implementation enforces a chunked 5 MB limit that aborts immediately on oversize payloads.
- **Design Note:** Ingesting 100 MB files requires streaming chunks directly to disk using `tempfile.SpooledTemporaryFile` with a background task queue (e.g., Celery or Python asyncio tasks) to prevent blocking ASGI worker threads during processing:
  ```python
  async def stream_upload_handler(request: Request, max_size_bytes: int = 104_857_600):
      spooled = tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024)
      bytes_read = 0
      async for chunk in request.stream():
          bytes_read += len(chunk)
          if bytes_read > max_size_bytes:
              spooled.close()
              raise HTTPException(status_code=413, detail="Payload exceeds 100 MB limit.")
          spooled.write(chunk)
      spooled.seek(0)
      return spooled
  ```

### 2.3 Threaded Inline Comments
- **Status:** I did not finish this feature in the time available. Finding-level decisions (`accept`, `modify`, `dismiss`) with mandatory rationale currently fulfill the governance requirement.
- **Design Note:** Free-form collaborative inline comments anchored to arbitrary text character spans will be implemented via an `audit_inline_comments` table:
  ```sql
  CREATE TABLE IF NOT EXISTS audit_inline_comments (
      id TEXT PRIMARY KEY,
      audit_id TEXT NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
      finding_id TEXT REFERENCES findings(id) ON DELETE SET NULL,
      author_user_id TEXT NOT NULL,
      char_start INTEGER NOT NULL,
      char_end INTEGER NOT NULL,
      comment_text TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open',
      created_at TEXT NOT NULL,
      resolved_at TEXT,
      FOREIGN KEY(audit_id) REFERENCES audits(id)
  );
  ```

### 2.4 Brand Vault Bulk Archive Import
- **Status:** I did not finish this feature in the time available. Programmatic REST API endpoints with idempotent migrations provide complete management capabilities.
- **Design Note:** Bulk vault migration will use an archive bundle format (`.loomshield-vault.json`) containing brand metadata, rules, terminology, verified facts, and approved logo assets with an Ed25519 signature of the archive manifest for integrity verification.

---

## 3. ARCHITECTURAL SKETCHES FOR UPCOMING CAPABILITIES

### 3.1 Production Identity & Tenancy (`docs/auth-plan.md`)
Production deployments require real enterprise authentication:
- **SSO & OIDC:** OpenID Connect (OIDC) and SAML 2.0 integration for Okta, Google Workspace, and Microsoft Entra ID.
- **Data Model:** Organizations owning Workspaces, which contain scoped Brand profiles and User memberships with role bindings (`admin`, `reviewer`, `creator`). Detailed in `docs/auth-plan.md`.

### 3.2 Hosted Database & Persistence
- **PostgreSQL Migration:** Transition from container-local SQLite to managed PostgreSQL (or Litestream-replicated SQLite) to ensure audit history, Brand Vault versions, and certificates survive cloud container redeployments.

### 3.3 Per-Visitor Demo Workspaces
- **Session Sandboxing:** Dynamically provision ephemeral SQLite databases or schema-isolated tenant workspaces per visitor session, automatically evicted after 60 minutes of inactivity.

### 3.4 Optical Character Recognition (OCR)
- **Local Raster OCR:** Integrate a lightweight, self-hosted OCR engine (e.g., ONNX-quantized text detector) to extract text coordinates and measure WCAG contrast on flattened bitmap images (.png, .jpg), extending the current vector SVG text contrast checker.

### 3.5 Evaluation & Telemetry Dashboard
- **Continuous Quality Monitoring:** Built-in benchmarking dashboard calculating ongoing Precision, Recall, and F1 across submitted audits, flagging rule drifts and regression anomalies over time.

### 3.6 Certificate Key Rotation
- **Key Directory & Grace Periods:** Support multiple Ed25519 public keys indexed by Key ID (`kid`), allowing scheduled rotation of active signing private keys while keeping previously issued compliance certificates verifiable throughout their validity window.

### 3.7 External Cryptographic Timestamping
- **RFC 3161 TSA Integration:** Anchor approved certificate digests against external cryptographic Timestamp Authorities (TSA) to generate independent cryptographic proof of the exact signing time without third-party blockchain gas fees.
