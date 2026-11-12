# MedShield — Interface Design System

## Intent

A working tool for people triaging chest X-rays and checking how each study was de-identified and stored.
It should look like dependable hospital software, not a product landing page: quiet, dense, legible, and
explicit about what the model's output does and does not mean.

## Structure

| Route | Name | Purpose |
|-------|------|---------|
| `/` | **Studies** | Upload / samples, priority-sorted study table with filters, detail panel for the open study |
| `/workstation` | **Viewer** | Original / de-identified (Cornerstone3D) / heatmap views, findings, study summary, shortcuts |
| `/security` | **Audit** | Pixel before/after, metadata de-identification table, encrypted storage, erase study, pipeline notes |

`/worklist` redirects to `/`. Navigation is a left sidebar (top bar below `md`). Every page starts with
`PageHeader` (title, one-line description, actions on the right).

## Rules

- **No marketing patterns.** No hero sections, eyebrow pills, "Step 01–04" strips, feature cards, sparkle/AI
  icons, or decorative icons in headings.
- **Color is information.** One interaction accent (blue). Red / amber / green only for clinical or security
  status (STAT, elevated/positive, removed/ok). Everything else is neutral gray.
- **Few badges.** Status is a dot + word (`PriorityLabel`) or colored text, not a pill. Avoid compliance-acronym
  badges; state facts in plain sentences instead.
- **Plain copy.** Sentence case, short labels ("Erase study", "Open in viewer"). No buzzwords ("zero-trust",
  "evidence-first", "enclave"). Never claim compliance or certification the code does not provide.
- **Model scores are not probabilities.** Show `Positive/Negative · 0.34` with the 0.50 threshold tick
  (`lib/scores.ts`); never a "% chance". Mark 0.40–0.60 as borderline.
- **Only real controls.** Every input must change something; no decorative form fields.

## Tokens (`frontend/src/styles/tokens.css`)

| Token | Value | Use |
|-------|-------|-----|
| `--bg-canvas` | `#F5F6F8` | Page background |
| `--bg-panel` | `#FFFFFF` | Sidebar, headers, panels, tables |
| `--bg-elevated` | `#EFF1F4` | Hover, selected nav, user chat bubble |
| `--bg-lightbox` | `#E8EAED` | Image stage behind radiographs |
| `--text-primary / -secondary / -muted` | `#16191D / #464E5A / #6A717C` | Text (muted ≥ 4.5:1 on white) |
| `--accent-brand` | `#1F5FBF` | Links, primary button, focus ring, selected-row marker |
| `--accent-critical` | `#B42318` | STAT, erase, errors |
| `--accent-attention` | `#A15C07` | Elevated / positive (non-STAT) |
| `--accent-verified` | `#087443` | Identifier removed / check passed |
| `--border-subtle / -strong` | `#E2E5E9 / #C9CED6` | Hairlines / control borders |

Radii: panels 6px, controls 4px, images 0–2px. Shadows only on floating layers (menus, tooltips, dialogs).

## Typography

System UI stack (`-apple-system, Segoe UI, Roboto, …`) for text and a system monospace stack for UIDs, hashes
and scores. No web fonts: nothing is fetched from third parties by a PHI-handling app. Body 13px, page titles
15px semibold, secondary text 12px.

## Components

- `PageHeader`, `Panel`, `StudyPicker` (`components/layout/`)
- `PriorityLabel`, `StudyDetail` (`components/study/`)
- `TriagePanel` = findings list (no card of its own; parent provides the container)
- Tables: white, no zebra striping, 1px row dividers, muted 12px headers.
