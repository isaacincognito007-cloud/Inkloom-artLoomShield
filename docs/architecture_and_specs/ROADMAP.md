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

## 2. STATUS & DESIGN NOTES FOR EXTENDED CAPABILITIES

Below is the status of extended capabilities from earlier planning rounds:

### 2.1 Presets for Existing Brands
- **Status:** Shipped in Round 3 Hardening.
- **Delivered:** Built-in multi-brand presets catalog (`novapay`, `verdant`, `acmecorp`, `finsafe`) with complete rule schemas, 11-column verified factual assertions, and official hex color palettes via `GET /api/brands/presets` and `POST /api/brands/presets/{preset_id}/apply` (`test_brand_presets_catalog_and_apply`).

### 2.2 Streaming Uploads & Render Safe Limit
- **Status:** Shipped in Round 3 Hardening.
- **Delivered:** Evaluated Render free instance container limits (512 MB RAM limit, 0.1 CPU). Rather than attempting 100 MB in-memory buffering which causes immediate container OOM crashes, implemented a safe maximum upload limit of 25 MB (`LOOMSHIELD_MAX_UPLOAD_MB=25`) with 64 KB streaming chunk reads, keeping peak memory under 280 MB (>220 MB RAM headroom), reported via `GET /api/system/limits` (`test_system_limits_and_render_free_profile`).

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
