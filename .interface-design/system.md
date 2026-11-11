# MedShield-AI Design System Tokens
**System ID:** `medshield-clean-pacs`  
**Standard:** Interface-Design System Architecture & UI/UX Pro Max  
**Theme:** Clinical Precision Dark (Swiss Minimalist Radiology)

---

## 1. Intent & Context
- **Target User:** Radiologist, Clinical Researcher, or Hospital Compliance Officer evaluating DICOM scans.
- **Environment:** Clinical reading room / low-ambient light workstation. High-contrast display required for fine radiograph features (consolidation, effusions).
- **Primary Goal:** Upload a radiograph $\rightarrow$ verify PII stripping & AES-256 seal $\rightarrow$ inspect primary AI diagnosis & Grad-CAM heatmap in under 5 seconds with zero cognitive clutter.
- **Feel:** Quiet, surgical, trusted, high-precision. No unnecessary sidebars, no noisy charts, no marketing fluff.

---

## 2. Color Palette & Semantic Tokens

### Primitives
```css
/* Surface & Obsidian Foundations */
--surface-bg:          #080C14; /* Deep radiologist room obsidian */
--surface-card:        #0E1524; /* Elevated container surface */
--surface-card-hover:  #141E33; /* Interactive hover layer */
--surface-subtle:      #18233C; /* Inset drag-drop zone & wells */
--surface-overlay:     rgba(8, 12, 20, 0.85); /* Backdrop blur */

/* Borders & Separators (Whisper-Quiet) */
--border-subtle:       #1E2A44; /* Clean 1px card boundaries */
--border-focus:        #0EA5E9; /* Accessible keyboard focus ring */
--border-divider:      #162035; /* Table & section divider lines */

/* Text & Readability (WCAG AAA / AA compliant on #080C14) */
--text-primary:        #F8FAFC; /* 100% white-slate for focal labels */
--text-secondary:      #94A3B8; /* 60% slate for supporting labels */
--text-muted:          #64748B; /* 40% slate for timestamps & metadata */
--text-on-accent:      #FFFFFF;

/* Clinical & Cryptographic Accents */
--accent-secure:       #10B981; /* Emerald 500 - TLS 1.3 / AES / PII Clean */
--accent-secure-bg:    rgba(16, 185, 129, 0.10);
--accent-secure-border:#059669;

--accent-ai:           #06B6D4; /* Cyan 500 - AI Model / Grad-CAM / Primary Finding */
--accent-ai-bg:        rgba(6, 182, 212, 0.10);
--accent-ai-border:    #0891B2;

--accent-alert:        #F59E0B; /* Amber 500 - Urgent / Elevated pathology triage */
--accent-alert-bg:     rgba(245, 158, 11, 0.12);

--accent-critical:     #EF4444; /* Rose 500 - STAT Critical pathology */
--accent-critical-bg:  rgba(239, 68, 68, 0.12);
```

### Semantic Token Aliases
| Semantic Token | Value | Applied To |
| :--- | :--- | :--- |
| `--color-app-bg` | `#080C14` | Body viewport background |
| `--color-card-bg` | `#0E1524` | 2-card main layout cards |
| `--color-card-border` | `#1E2A44` | 1px card borders |
| `--color-badge-secure` | `#10B981` | "System Secure" & "PII Stripped" badges |
| `--color-confidence-fill` | `#06B6D4` $\rightarrow$ `#3B82F6` | Confidence progress bar gradient |
| `--color-heatmap-toggle` | `#0EA5E9` | "Show AI Heatmap" active state |

---

## 3. Typography Scale

- **UI Headings & Body:** `Inter`, `Plus Jakarta Sans`, or `system-ui, -apple-system, sans-serif`
- **Clinical UIDs & Crypto Hashes:** `JetBrains Mono`, `ui-monospace`, `monospace`

```css
/* Typography Scale */
--font-sans: 'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Menlo', monospace;

/* Type Scale (Fluid & Compact) */
--text-2xs:  0.6875rem; /* 11px - Micro badges & DICOM hex tags */
--text-xs:   0.75rem;   /* 12px - Secondary captions & metadata */
--text-sm:   0.875rem;  /* 14px - Body text & toggle labels */
--text-base: 1.0rem;    /* 16px - Standard labels & button text */
--text-lg:   1.125rem;  /* 18px - Top finding title */
--text-xl:   1.25rem;   /* 20px - Card headers */
```

---

## 4. Spacing, Radii & Depth

### Spacing Scale (8px Grid)
- `space-1` (4px): Micro gaps between icons and labels
- `space-2` (8px): Padding in small chips, toggle switches
- `space-3` (12px): Standard inner button and input padding
- `space-4` (16px): Card inner padding on mobile
- `space-6` (24px): Card inner padding on desktop
- `space-8` (32px): Gap between the 2 primary cards

### Border Radii
- `radius-sm`: `6px` (Badges, toggle switches, code chips)
- `radius-md`: `10px` (Buttons, dropzone wells)
- `radius-lg`: `16px` (Main side-by-side cards)

### Depth & Elevation
- **Strategy:** *Borders-only with subtle surface shifts* (strictly avoiding noisy dropshadows that compete with radiology contrast).
- Card shadow: `0 4px 20px -2px rgba(0, 0, 0, 0.5)`
- Focus ring: `0 0 0 2px #0EA5E9, 0 0 0 4px rgba(14, 165, 233, 0.2)`

---

## 5. Component Style Specs

### Top Bar
- Height: `56px` fixed
- Content:
  - Left: MedShield-AI Logo Mark + App Title (`MedShield-AI` + small `Clinical Diagnostic & Security Console`)
  - Right: Minimal pill `<span class="pill-secure"><span class="dot-pulse"></span> System Secure (AES-256 / TLS 1.3)</span>`

### Left Card: Image & Radiograph Stage
- Empty State: Clean dashed dropzone with cloud upload icon + "Drop DICOM (.dcm) or Scan (.png) here or browse" + 3 tiny quick-case chips (`Pneumonia`, `Effusion`, `Cardiomegaly`).
- Loaded State: 
  - Centered high-resolution radiograph display inside black viewport (`#000000`).
  - Bottom bar with a single clean pill toggle:
    `[ Switch ] Show AI Heatmap (Grad-CAM)`
  - Sub-toggle option (appears only if heatmap active): Pathology selector pills (`Pneumonia`, `Cardiomegaly`, etc.).

### Right Card: Diagnosis & Security Summary
- Section 1: Primary AI Prediction
  - Top Finding Name (e.g. `Pneumonia (Consolidation)`) in large high-contrast typography (`text-lg font-bold text-white`).
  - Clean confidence bar (e.g. `81.2% Confirmed`) with animated smooth fill (`transition: width 400ms ease-out`).
  - Small secondary findings collapsed into 1 clean line (e.g. *Also screened: Infiltration 65.4%, Effusion 18.2%*).
- Section 2: Compact Security Badge & Drawer
  - Compact badge: `[ ✓ PII Stripped • AES-256 Encrypted ]` (Emerald status chip).
  - Expandable trigger: `[ ▾ View Stripped DICOM Tags & Hash ]` (collapsed by default).
  - When expanded: 
    * 1-click copy for SHA-256 ciphertext hash.
    * Clean table of stripped PII tags (`PatientName`, `PatientID`, `DOB`, `Institution`, etc.).
- Section 3: Action Buttons
  - Primary button: `Download Decrypted Scan (.dcm / .png)`
  - Secondary subtle link/button: `Crypto-Shred Study (DPDP Erasure)`

