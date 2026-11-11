# MedShield-AI — Interface Design System

## Intent

**Who is this human?** A radiologist, security officer, or clinical researcher at a hospital workstation. They've just received imaging studies from the PACS. It's a work environment — overhead fluorescents, maybe a second coffee, reading dozens of scans in a shift. They need to trust this tool the way they trust their PACS viewer: quiet authority, zero flash, everything where they expect it.

**What must they accomplish?** Three verbs in sequence: **Ingest** a study → **Verify** it was properly de-identified and encrypted → **Read** the AI diagnosis with a heatmap overlay. Secondary: exercise the right-to-erasure for a specific study.

**What should this feel like?** Like a light box in a reading room. Not a SaaS dashboard. Not a trading terminal. The X-ray is the center of the universe — everything else exists to annotate it. Calm, precise, institutional. The kind of tool where you notice the typography is good but can't say why. Dense without feeling cramped. Dark because radiologists read in the dark.

## Domain Exploration

**Domain concepts:** Light box, reading room, film alternator, window/level adjustment, annotation overlay, study jacket, radiology report dictation, PACS hanging protocol, differential diagnosis.

**Color world — what exists naturally here:**
- The blue-white glow of a backlit film on a light box
- The warm amber of a desk lamp in a dark reading room
- The clinical green of a status indicator on medical equipment
- The deep navy of hospital scrubs
- The cool gray of stainless steel exam furniture
- The red of a STAT priority stamp

**Signature element:** The film viewer is the product. Not a generic image preview — a purpose-built viewport with a subtle vignette that mimics the falloff of a real light box. The radiograph floats in darkness the way a film hangs on an alternator.

**Defaults to reject:**
1. ~~Neon cyan accent everywhere~~ → Reserved emerald for "verified/safe", muted amber for "attention needed"
2. ~~Card grid with identical rounded corners~~ → Asymmetric layout: image dominates left 60%, metadata stacks right
3. ~~Gradient washes and glow effects~~ → Flat surfaces with single-pixel borders, depth through lightness only

## Palette

Built from the reading room, not a SaaS template.

| Token | Hex | Why |
|-------|-----|-----|
| `--surface-0` (base) | `#0C0E13` | Near-black. Radiologists read in the dark. Not pure black — has a trace of warm blue. |
| `--surface-1` (panel) | `#13161D` | One step up. Sidebar, cards. Barely perceptible lift. |
| `--surface-2` (elevated) | `#1A1D26` | Popovers, dropdowns, hovered rows. |
| `--surface-3` (input) | `#0F1117` | Inputs are inset — slightly darker than their container. |
| `--border` | `rgba(255,255,255,0.07)` | Invisible until you need structure. |
| `--border-focus` | `rgba(255,255,255,0.16)` | Focus rings, active borders. |
| `--text-primary` | `#E8E9ED` | High contrast on dark. Not pure white — slightly warm. |
| `--text-secondary` | `#A0A5B1` | Labels, metadata, supporting copy (WCAG AA compliant). |
| `--text-muted` | `#787D8A` | Tertiary, timestamps, disabled (>= 4.5:1 on `#13161D`). |
| `--accent-verified` | `#34D399` | Emerald. "Sanitized", "Encrypted", "Passed". Security = green. |
| `--accent-attention` | `#FBBF24` | Amber. Elevated triage, warnings, pending. |
| `--accent-critical` | `#F87171` | Soft red. STAT critical, errors, crypto-shred confirmation. |
| `--accent-info` | `#60A5FA` | Blue. Neutral informational — links, model metadata. |

**60/30/10 rule:** 60% `--surface-0` and `--surface-1` (the dark canvas). 30% text hierarchy (`--text-primary` through `--text-muted`). 10% accent colors, and most of that is `--accent-verified` on security badges.

## Typography

**Typeface:** IBM Plex Sans (body/UI) + IBM Plex Mono (data/hashes/hex).

**Why IBM Plex?** It was designed for interfaces that display technical data. It has a medical-grade neutrality — no personality to fight the content, wide x-height for small sizes, and a mono companion that shares the same vertical metrics. Not Inter (everyone's default). Not Figtree (too soft for a security tool).

**Scale (ratio 1.2, base 13px — dense dashboard):**
| Level | Size | Weight | Color | Tracking | Use |
|-------|------|--------|-------|----------|-----|
| Display | 20px | 600 | `--text-primary` | -0.02em | Page title only |
| H1 | 17px | 600 | `--text-primary` | -0.01em | Section headers |
| H2 | 14px | 600 | `--text-primary` | 0 | Panel headers |
| Body | 13px | 400 | `--text-primary` | 0 | Default |
| Label | 11px | 500 | `--text-secondary` | 0.02em | Field labels, column heads |
| Caption | 10px | 400 | `--text-muted` | 0.01em | Timestamps, fine print |
| Mono | 12px | 400 | varies | 0 | Hashes, hex, UIDs, entropy values |

## Spacing

**Base unit:** 4px. Dense dashboard density (8–32px scale).

| Token | Value | Use |
|-------|-------|-----|
| `--space-1` | 4px | Icon gaps, inline padding |
| `--space-2` | 8px | Component internal padding |
| `--space-3` | 12px | Between related elements |
| `--space-4` | 16px | Panel padding |
| `--space-5` | 20px | Between groups |
| `--space-6` | 24px | Section gaps |

## Depth Strategy

**Borders only** — no shadows. This is a technical tool, not a consumer app. Structure comes from 1px borders at `rgba(255,255,255,0.07)` and subtle surface-color shifts. No glow, no blur, no glassmorphism.

## Border Radius

| Element | Radius |
|---------|--------|
| Buttons, badges, inputs | 6px |
| Cards, panels | 8px |
| The viewport (film viewer) | 4px (nearly square — medical imaging is precise) |
| Modals | 12px |

## Layout

Three-column asymmetric grid:
- **Left (240px fixed):** Study ingestion panel — upload zone, sample cases, system spec. Compact, stacked, always visible.
- **Center (fluid, ~60% of remaining):** The film viewer. This is the focal point. Minimum 500px height. Below it: the PII audit table.
- **Right (320px fixed):** Diagnostics and security panels stacked vertically. AI predictions, crypto verification, DPDP erasure.

On screens < 1024px: stack to single column, image first.

## States

Every interactive element has: default, hover (`--surface-2` background shift), active (scale 0.97), focus (2px ring `--border-focus`), disabled (0.4 opacity).

## Component Patterns

**Status badge:** Pill shape. Background is the accent color at 10% opacity, text is the accent color at full, 1px border at 20%. Three variants: verified (emerald), attention (amber), critical (red).

**Metric display:** Label (11px/500/secondary) above value (17px/600/primary) with unit suffix (11px/400/muted). Not a card — just stacked text with controlled whitespace.

**PII table:** Monospace values. Alternating row backgrounds (`--surface-0` / `--surface-1`). Status column right-aligned with badge.

**Film viewport:** Black background with subtle radial light-box vignette falloff. Dual-layer rendering: de-identified base scan beneath the Grad-CAM overlay so opacity slider blends anatomy cleanly without dimming. Includes PACS Invert (`I`), Pan-on-Zoom, and scroll-wheel zoom. Overlay control dock visible on focus/hover/touch. No permanent chrome obscuring the image.

**Interactive Pathology Linking:** Selecting any prediction row in the Diagnostics panel switches to the Grad-CAM view for that specific pathology and surfaces epistemic uncertainty alongside confidence.

**Inline Destructive Confirmation:** Crypto-shredding uses an inline two-step arm/confirm control in place of browser modal dialogs (`alert`/`confirm`).

