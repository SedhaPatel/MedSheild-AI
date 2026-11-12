# MedShield-AI — Daylight Clinical Multi-Page Design System

## Intent

**Who is this human?** A clinician, radiologist, hospital privacy officer, or clinical engineer working at a sunlit hospital workstation or ambulatory clinic monitor. They need calm, effortless clarity across intake, reading, and cryptographic compliance verification.

**What must they accomplish?** Move fluidly across dedicated, uncluttered pages matching real hospital workflows:
1. **Clinical Overview (`/`)** — Assess workstation posture, regulatory readiness (HIPAA Safe Harbor, FIPS 140-3, DPDP Act Sec. 12), pipeline architecture, and launch studies.
2. **Worklist & Ingestion (`/worklist`)** — Drop raw `.dcm` / thoracic scans or trigger reference cases, search/filter the triage queue (`STAT_CRITICAL`, `ELEVATED`, `ROUTINE`), and route directly to reading or audit.
3. **PACS Reading Workstation (`/workstation`)** — Inspect de-identified DICOM studies inside a bright clinical Cornerstone3D porcelain viewport with W/L, Pan, Invert, Zoom, Grad-CAM localization mix, and differential diagnostic triage.
4. **Security & Safe Harbor Vault (`/security`)** — Verify Original vs. Burned-in Pixel Redacted scans side-by-side, inspect the full 18-tag DICOM PS 3.15 Annex E Safe Harbor diff table, check AES-256-GCM Shannon entropy (`>= 7.99 bits/byte`), copy SHA-256 hashes, inspect the 64-byte `MEDENC01` header, and execute irreversible two-step DPDP Sec. 12 Crypto-Shredding.

**What should this feel like?** A high-precision Swiss clinical portal built for daylight monitors: crisp white institutional surfaces layered over porcelain alabaster `#F7FAFC`, fine slate hairlines `#E2E8F0`, zero dark chrome, and zero glowing text or neon halation.

## Non-Negotiable Visual Rules
- **Strictly Light Surfaces:** All page backgrounds, navigation headers, sidebars, cards, viewports, modal overlays, tooltips, and badges use bright daylight hues (`#FFFFFF`, `#F7FAFC`, `#F1F5F9`, `#EEF3F8`). Never dark/black/charcoal chrome.
- **No Glowing Text:** Strictly `text-shadow: none` globally; matte deep slate ink (`#1E293B`, `#475569`, `#64748B`) and matte clinical accents (`#0284C7`, `#0F766E`, `#047857`, `#B45309`, `#B91C1C`) for sharp optical clarity.

## Palette & Tokens

| Token | Hex | Role |
|-------|-----|------|
| `--bg-canvas` | `#F7FAFC` | Porcelain alabaster base page canvas |
| `--bg-panel` | `#FFFFFF` | Elevated white institutional cards, headers, side rails |
| `--bg-elevated` | `#F1F5F9` | Cool ice mist rows, subtle tabs, pill containers |
| `--bg-input` | `#F8FAFC` | Whisper porcelain inputs and hex wells |
| `--bg-lightbox` | `#EEF3F8` | Bright porcelain radiograph PACS viewport stage |
| `--bg-backdrop` | `rgba(241, 245, 249, 0.82)` | Frosted light modal overlay |
| `--text-primary` | `#1E293B` | Crisp matte slate primary typography |
| `--text-secondary` | `#475569` | Secondary labels and table copy |
| `--text-muted` | `#64748B` | Tertiary hints, UIDs, timestamps (>= 4.6:1 on white) |
| `--accent-brand` | `#0284C7` | Primary clinical cerulean CTA, active route & focus ring |
| `--accent-teal` | `#0F766E` | Surgical teal cryptography & pipeline highlights |
| `--accent-verified` | `#047857` | Matte botanical emerald ("Sanitized", "Passed") |
| `--accent-attention` | `#B45309` | Matte ochre amber ("Elevated", "Warning") |
| `--accent-critical` | `#B91C1C` | Matte triage crimson ("STAT Critical", "Shredded") |
| `--accent-info` | `#0369A1` | Matte medical cobalt ("Info", "AI Model") |
| `--border-subtle` | `#E2E8F0` | 1px daylight hairline |
| `--border-strong` | `#CBD5E1` | Interactive control border |

## Typography
- **Display / Headings:** `Figtree` — clean architectural warmth suited to healthcare portals.
- **Body UI:** `Noto Sans` — wide apertures, high legibility in multi-column tables and clinical guidance.
- **Technical / Cryptographic Mono:** `IBM Plex Mono` (`tabular-nums`) — DICOM tag hexes, UIDs, Shannon entropy values, SHA-256 checksums, `MEDENC01` header previews.

## Scan Chat Slide-Over Drawer (`ScanChatDrawer`)
- **Trigger:** Single `"Ask AI About This Scan"` soft cerulean pill inside Card 2 (`OverviewPage`) and optional workstation bar; main 2-card dashboard grid remains unchanged.
- **Container & Surface:** Fixed right-side `@radix-ui/react-dialog` sheet (`420px` desktop width, `100%` mobile), pure white surface (`--bg-panel`), left hairline (`1px solid --border-strong`), frosted light backdrop (`--bg-backdrop`), `text-shadow: none`.
- **Message Hierarchy:**
  - User bubbles: `--accent-brand-soft` (`#E0F2FE`) fill, `--accent-brand-border`, matte `--text-primary`.
  - Assistant bubbles: `--bg-canvas` (`#F8FAFC`), `--border-subtle`, grounded finding tags (`--accent-teal` / `--accent-verified`), persistent `--accent-attention-soft` clinical scope disclaimer banner.
  - 3 Starter Quick Chips: full-pill outlines (`--border-strong`, `--bg-panel`, hover `--bg-elevated`), visible `2px solid --border-focus` keyboard focus ring, IME composition-safe `Enter` submission.

