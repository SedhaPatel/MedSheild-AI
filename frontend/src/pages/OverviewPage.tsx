import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Activity,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Eye,
  Lock,
  MessageSquareText,
  Monitor,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { IngestionDropzone } from '@/components/sidebar/IngestionDropzone'
import { cn } from '@/lib/utils'
import {
  selectIsActiveStudyShredded,
  useWorkstationStore,
} from '@/stores/useWorkstationStore'

const PATHOLOGIES = [
  'Pneumonia',
  'Cardiomegaly',
  'Pleural Effusion',
  'Pneumothorax',
  'Atelectasis',
] as const

const CARE_SETTINGS = ['Emergency Triage', 'Inpatient Ward', 'Routine Screening'] as const

const PATHOLOGY_EVIDENCE_GUIDE: Record<
  string,
  { cues: string; lookalikes: string; summary: string }
> = {
  Pneumonia: {
    summary: 'Focal or lobar airspace opacification consistent with pulmonary consolidation.',
    cues: 'Asymmetric hazy lobar shadow, air bronchograms, blurred hemidiaphragm silhouette.',
    lookalikes: 'Atelectasis volume loss, pulmonary edema, or overlapping pleural effusion.',
  },
  Cardiomegaly: {
    summary: 'Enlarged cardiac silhouette with increased cardiothoracic transverse ratio.',
    cues: 'Cardiac shadow spanning over half the internal thoracic diameter on PA projection.',
    lookalikes: 'AP projection geometric magnification, pericardial effusion, or elevated diaphragm.',
  },
  'Pleural Effusion': {
    summary: 'Dependent fluid density blunting one or both costophrenic angles.',
    cues: 'Concave meniscus contour tracking along the lateral chest wall with homogenous lower opacity.',
    lookalikes: 'Pleural thickening, elevated hemidiaphragm, or lower lobe consolidation.',
  },
  Pneumothorax: {
    summary: 'Pleural air separation showing absent distal pulmonary vascular markings.',
    cues: 'Sharp thin white visceral pleural edge bordered by peripheral lucent air space.',
    lookalikes: 'Skin fold artifact on bedside AP studies, apical bullae, or scapular border.',
  },
  Atelectasis: {
    summary: 'Linear or platelike pulmonary parenchymal collapse with localized volume shift.',
    cues: 'Band-like density, slight fissure displacement, or elevated ipsilateral hemidiaphragm.',
    lookalikes: 'Post-infectious scarring, subsegmental consolidation, or hypoventilation.',
  },
}

const HOW_IT_WORKS = [
  {
    step: '01',
    title: 'Upload or Paste Radiograph',
    body: 'Drop a DICOM (.dcm) study, browse a PNG/JPEG chest film, press Ctrl+V from clipboard, or select a clinical sample.',
  },
  {
    step: '02',
    title: 'Strip PHI & Mask Burned-In Text',
    body: 'Scrubs 18 HIPAA Safe Harbor metadata tags and masks burned-in corner text before downstream inspection.',
  },
  {
    step: '03',
    title: 'Seal in AES-256-GCM Vault',
    body: 'Encrypts sanitized DICOM bytes inside an authenticated MEDENC01 envelope with a dedicated study KEK.',
  },
  {
    step: '04',
    title: 'Evidence-First AI Triage',
    body: 'Generates 5-class probability rankings, epistemic uncertainty bounds, and spatially aligned Grad-CAM heatmaps.',
  },
] as const

function confidenceMeta(probability: number, uncertainty: number) {
  if (probability >= 0.7 && uncertainty < 0.08) {
    return { label: 'High Confidence', variant: 'verified' as const }
  }
  if (probability >= 0.4) {
    return { label: 'Moderate Confidence', variant: 'attention' as const }
  }
  return { label: 'Uncertain — Clinical Correlation Needed', variant: 'neutral' as const }
}

export function OverviewPage() {
  const navigate = useNavigate()
  const samples = useWorkstationStore((s) => s.samples)
  const worklist = useWorkstationStore((s) => s.worklist)
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const activeSampleId = useWorkstationStore((s) => s.activeSampleId)
  const targetPathology = useWorkstationStore((s) => s.targetPathology)
  const ingestSample = useWorkstationStore((s) => s.ingestSample)
  const changePathologyHeatmap = useWorkstationStore((s) => s.changePathologyHeatmap)
  const setChatOpen = useWorkstationStore((s) => s.setChatOpen)
  const previewHeatmap = useWorkstationStore((s) => s.previewHeatmap)
  const setPreviewHeatmap = useWorkstationStore((s) => s.setPreviewHeatmap)

  const [careSetting, setCareSetting] = useState<(typeof CARE_SETTINGS)[number]>('Emergency Triage')
  const [clinicalNotes, setClinicalNotes] = useState('')

  const isShredded = useWorkstationStore(selectIsActiveStudyShredded)
  const isChatDisabled = !activeStudy || isShredded
  const chatTooltipText = !activeStudy
    ? 'Upload or select a scan first'
    : isShredded
      ? 'Study erased under DPDP Sec. 12'
      : undefined

  const predictions = activeStudy?.ai_diagnostics.predictions ?? []
  const topFinding = predictions[0]
  const alternatives = predictions.slice(1, 5)
  const topGuide = topFinding ? PATHOLOGY_EVIDENCE_GUIDE[topFinding.pathology] : undefined
  const confidenceInfo = topFinding
    ? confidenceMeta(topFinding.probability, topFinding.epistemic_uncertainty)
    : null
  const sanitizedCount =
    activeStudy?.deidentification.tag_diff_matrix.filter((r) => r.status === 'SANITIZED').length ??
    0
  const totalTags = activeStudy?.deidentification.tag_diff_matrix.length ?? 18

  return (
    <div className="flex-1 bg-bg-canvas">
      {/* Band 1: Centered Daylight Hero + Interactive Identifier Workbench */}
      <section className="border-b border-border-subtle bg-bg-panel px-4 py-8 sm:px-6 lg:py-10">
        <div className="mx-auto max-w-[1360px] space-y-7">
          {/* Editorial Hero Header */}
          <div className="mx-auto max-w-3xl space-y-3 text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-accent-teal-border bg-accent-teal-soft px-3 py-1 text-[11px] font-semibold text-accent-teal">
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
              <span>HIPAA Safe Harbor &middot; FIPS 140-3 AES-GCM &middot; Evidence-First AI</span>
            </div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
              De-Identify &amp; Analyze Chest Radiographs with Clear Visual Evidence
            </h1>
            <p className="mx-auto max-w-2xl text-xs leading-relaxed text-text-secondary sm:text-sm">
              Upload a DICOM study or chest X-ray image to strip patient identifiers, seal the record with authenticated encryption, and inspect ranked pathology findings with epistemic uncertainty and Grad-CAM localization.
            </p>
          </div>

          {/* Interactive Two-Column Identifier Card */}
          <div className="grid grid-cols-1 gap-6 rounded-[var(--dialog-radius)] border border-border-strong bg-bg-canvas p-4 sm:p-6 lg:grid-cols-[1.02fr_1fr]">
            {/* Left Column: Upload, Optional Context & Reference Samples */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-sm font-semibold text-text-primary">
                  1. Radiograph Input &amp; Clinical Context
                </h2>
                <span className="text-[11px] font-medium text-text-muted">
                  Zero PHI persisted
                </span>
              </div>

              <IngestionDropzone enableClipboardPaste />

              {/* Framing & Image Quality Tip Box */}
              <div className="rounded-[var(--control-radius)] border border-accent-info-border bg-accent-info-soft px-3.5 py-2.5 text-[11px] leading-relaxed text-text-secondary">
                <strong className="font-semibold text-accent-info">Capture tip:</strong> Frontal PA or AP chest studies give clearest lung field coverage. Any patient overlay text in image corners is automatically redacted.
              </div>

              {/* Optional Context Selectors (SnapIdentify-inspired) */}
              <div className="space-y-3 rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold text-text-secondary">
                    Target Pathology Focus
                  </span>
                  <Select
                    value={targetPathology}
                    onValueChange={(val) => {
                      void changePathologyHeatmap(val)
                    }}
                  >
                    <SelectTrigger aria-label="Target pathology heatmap focus" className="min-w-[165px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PATHOLOGIES.map((p) => (
                        <SelectItem key={p} value={p}>
                          {p}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <span className="block text-[11px] font-semibold text-text-secondary">
                    Care Setting Context
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {CARE_SETTINGS.map((setting) => (
                      <button
                        key={setting}
                        type="button"
                        onClick={() => setCareSetting(setting)}
                        className={cn(
                          'cursor-pointer rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors',
                          careSetting === setting
                            ? 'border-accent-brand-border bg-accent-brand-soft font-semibold text-accent-brand-hover'
                            : 'border-border-subtle bg-bg-input text-text-secondary hover:bg-bg-elevated'
                        )}
                      >
                        {setting}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="clinical-notes"
                    className="mb-1 block text-[11px] font-semibold text-text-secondary"
                  >
                    Optional Clinical Notes (local session only)
                  </label>
                  <input
                    id="clinical-notes"
                    type="text"
                    value={clinicalNotes}
                    onChange={(e) => setClinicalNotes(e.target.value)}
                    placeholder="e.g., febrile cough 4 days, baseline PA view"
                    className="h-8 w-full rounded-[var(--control-radius)] border border-border-subtle bg-bg-input px-2.5 text-xs text-text-primary placeholder:text-text-muted focus-visible:outline-2 focus-visible:outline-border-focus"
                  />
                </div>
              </div>

              {/* Instant Sample Cases */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold tracking-wide text-text-secondary uppercase">
                    Or Try Validated Reference Cases
                  </span>
                  <Link
                    to="/worklist"
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-accent-brand hover:text-accent-brand-hover"
                  >
                    <span>Queue ({worklist.length})</span>
                    <ArrowRight className="h-3 w-3" aria-hidden="true" />
                  </Link>
                </div>

                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {samples.length === 0 ? (
                    <div className="col-span-full rounded-[var(--control-radius)] border border-border-subtle bg-bg-panel px-3 py-2.5 text-xs text-text-muted">
                      Connecting to MedShield clinical API...
                    </div>
                  ) : (
                    samples.map((sample) => {
                      const isSelected = activeSampleId === sample.id
                      return (
                        <button
                          key={sample.id}
                          type="button"
                          onClick={() => {
                            void ingestSample(sample.id)
                          }}
                          className={cn(
                            'cursor-pointer rounded-[var(--control-radius)] border px-3 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-border-focus',
                            isSelected
                              ? 'border-accent-brand-border bg-accent-brand-soft'
                              : 'border-border-subtle bg-bg-panel hover:border-border-strong hover:bg-bg-elevated'
                          )}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-xs font-semibold text-text-primary">
                              {sample.name.replace(/^Patient \d+: /, '')}
                            </span>
                            <Badge variant="attention">Sample</Badge>
                          </div>
                          <div className="mt-0.5 truncate text-[11px] text-text-muted">
                            {sample.finding}
                          </div>
                        </button>
                      )
                    })
                  )}
                </div>
              </div>
            </div>

            {/* Right Column: Structured Evidence & Diagnostic Results Card */}
            <div className="flex flex-col rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel">
              <div className="flex items-center justify-between border-b border-border-subtle bg-bg-input px-4 py-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-accent-teal" aria-hidden="true" />
                  <h2 className="font-display text-sm font-semibold text-text-primary">
                    2. Diagnostic Evidence &amp; Safety Report
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span
                        className="inline-flex"
                        tabIndex={isChatDisabled ? 0 : undefined}
                      >
                        <Button
                          variant="soft"
                          size="sm"
                          disabled={isChatDisabled}
                          onClick={() => setChatOpen(true)}
                          className="gap-1.5"
                        >
                          <MessageSquareText className="h-3.5 w-3.5" aria-hidden="true" />
                          <span>Ask AI About This Scan</span>
                        </Button>
                      </span>
                    </TooltipTrigger>
                    {chatTooltipText && (
                      <TooltipContent>{chatTooltipText}</TooltipContent>
                    )}
                  </Tooltip>
                  {activeStudy && confidenceInfo ? (
                    <Badge variant={confidenceInfo.variant}>{confidenceInfo.label}</Badge>
                  ) : (
                    <Badge variant="neutral">Awaiting Study</Badge>
                  )}
                </div>
              </div>

              {!activeStudy || !topFinding ? (
                <div className="flex flex-1 flex-col justify-between gap-4 p-5">
                  <div className="space-y-3">
                    <p className="text-xs leading-relaxed text-text-secondary">
                      Once a chest study is uploaded or selected, this summary breaks down:
                    </p>
                    <ul className="space-y-2 text-xs text-text-secondary">
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-verified" aria-hidden="true" />
                        <span>
                          <strong className="font-semibold text-text-primary">Primary match &amp; uncertainty:</strong> top AI pathology estimate with Monte-Carlo Dropout variance.
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-verified" aria-hidden="true" />
                        <span>
                          <strong className="font-semibold text-text-primary">Visual cues &amp; lookalikes:</strong> radiographic patterns explaining the score alongside alternative diagnoses.
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-verified" aria-hidden="true" />
                        <span>
                          <strong className="font-semibold text-text-primary">HIPAA &amp; encryption proof:</strong> count of sanitized DICOM attributes and AES-256-GCM Shannon entropy.
                        </span>
                      </li>
                    </ul>
                  </div>

                  {samples[0] && (
                    <Button
                      variant="primary"
                      onClick={() => {
                        void ingestSample(samples[0].id)
                      }}
                    >
                      <span>Run Sample Study Now</span>
                      <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                    </Button>
                  )}
                </div>
              ) : (
                <div className="flex flex-1 flex-col justify-between gap-4 p-5">
                  {/* Top Match Preview + Preview Toggle */}
                  <div className="space-y-4">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                      <div className="relative h-32 w-32 shrink-0 overflow-hidden rounded-[var(--viewport-radius)] border border-border-strong bg-bg-lightbox p-1">
                        <img
                          src={activeStudy.images.redacted_image_url}
                          alt="Sanitized thoracic preview"
                          className="h-full w-full object-contain"
                        />
                        {previewHeatmap && (
                          <img
                            src={activeStudy.images.gradcam_heatmap_url}
                            alt="Grad-CAM saliency overlay"
                            className="pointer-events-none absolute inset-1 h-[calc(100%-8px)] w-[calc(100%-8px)] object-fill opacity-75"
                          />
                        )}
                      </div>

                      <div className="min-w-0 flex-1 space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-display text-lg font-bold text-text-primary">
                            {topFinding.pathology}
                          </span>
                          <Badge
                            variant={
                              activeStudy.ai_diagnostics.overall_triage_urgency === 'STAT_CRITICAL'
                                ? 'critical'
                                : activeStudy.ai_diagnostics.overall_triage_urgency === 'ELEVATED'
                                  ? 'attention'
                                  : 'verified'
                            }
                          >
                            {(topFinding.probability * 100).toFixed(1)}% (&plusmn;
                            {topFinding.epistemic_uncertainty.toFixed(3)})
                          </Badge>
                        </div>

                        <p className="text-xs leading-relaxed text-text-secondary">
                          {topGuide?.summary ?? 'Radiographic opacity pattern prioritized for clinical inspection.'}
                        </p>

                        <div className="flex flex-wrap items-center gap-2 pt-1">
                          <button
                            type="button"
                            onClick={() => setPreviewHeatmap((v: boolean) => !v)}
                            className="cursor-pointer rounded-[var(--control-radius)] border border-accent-brand-border bg-accent-brand-soft px-2.5 py-1 text-[11px] font-semibold text-accent-brand-hover transition-colors hover:bg-accent-info-soft"
                          >
                            {previewHeatmap ? 'Hide Grad-CAM Overlay' : 'Preview Grad-CAM Overlay'}
                          </button>
                          <span className="font-mono text-[11px] text-text-muted">
                            {careSetting} &middot; {activeStudy.ai_diagnostics.inference_latency_ms} ms
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Visible Evidence Cues + Differential Lookalikes */}
                    {topGuide && (
                      <div className="grid grid-cols-1 gap-2.5 rounded-[var(--control-radius)] border border-border-subtle bg-bg-input p-3 text-xs sm:grid-cols-2">
                        <div>
                          <div className="text-[11px] font-semibold text-text-primary">
                            Visible Radiographic Cues
                          </div>
                          <p className="mt-0.5 text-[11px] leading-relaxed text-text-secondary">
                            {topGuide.cues}
                          </p>
                        </div>
                        <div>
                          <div className="text-[11px] font-semibold text-text-primary">
                            Key Lookalikes to Rule Out
                          </div>
                          <p className="mt-0.5 text-[11px] leading-relaxed text-text-secondary">
                            {topGuide.lookalikes}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Alternative Differential Candidates */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] font-semibold text-text-secondary">
                        <span>Alternative Matches &amp; Differential Breakdown</span>
                        <span className="font-mono text-text-muted">Ranked by confidence</span>
                      </div>
                      <div className="space-y-1.5">
                        {alternatives.map((item) => {
                          const pct = (item.probability * 100).toFixed(1)
                          return (
                            <div
                              key={item.pathology}
                              className="grid grid-cols-[120px_1fr_48px] items-center gap-2 text-xs"
                            >
                              <span className="truncate font-medium text-text-primary">
                                {item.pathology}
                              </span>
                              <div className="h-1.5 overflow-hidden rounded-full bg-bg-elevated">
                                <div
                                  className="h-full rounded-full bg-accent-brand"
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <span className="text-right font-mono text-[11px] text-text-secondary tabular-nums">
                                {pct}%
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {/* Inline Security Compliance Summary */}
                    <div className="flex flex-wrap items-center gap-2 border-t border-border-subtle pt-3">
                      <Badge variant="verified">
                        {sanitizedCount}/{totalTags} Safe Harbor Tags Scrubbed
                      </Badge>
                      <Badge variant="teal">
                        H={activeStudy.security.shannon_entropy_bits_per_byte.toFixed(4)} bits/B
                      </Badge>
                      <Badge variant="neutral">
                        {activeStudy.deidentification.burned_in_text_redacted
                          ? 'Corner Text Masked'
                          : 'No Overlay PHI'}
                      </Badge>
                    </div>
                  </div>

                  {/* Direct Navigation CTAs into Specialized Views */}
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                    <Button variant="primary" onClick={() => navigate('/workstation')}>
                      <Monitor className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>PACS Viewer</span>
                    </Button>
                    <Button variant="outline" onClick={() => navigate('/security')}>
                      <Lock className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>Security Vault</span>
                    </Button>
                    <Button variant="outline" onClick={() => navigate('/worklist')}>
                      <ClipboardList className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>Worklist ({worklist.length})</span>
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Band 2: How It Works (4-Step Airy Daylight Process Strip) */}
      <section className="border-b border-border-subtle bg-bg-tint px-4 py-10 sm:px-6">
        <div className="mx-auto max-w-[1360px] space-y-5">
          <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
            <div>
              <h2 className="font-display text-lg font-bold text-text-primary">
                How Zero-Trust Study Identification Works
              </h2>
              <p className="text-xs text-text-secondary">
                Every radiograph travels through deterministic sanitization and FIPS-aligned sealing before rendering.
              </p>
            </div>
            <Link
              to="/security"
              className="inline-flex items-center gap-1 text-xs font-semibold text-accent-teal hover:underline"
            >
              <span>Explore cryptographic vault</span>
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {HOW_IT_WORKS.map((item) => (
              <div
                key={item.step}
                className="rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel p-4"
              >
                <span className="inline-block rounded-full border border-accent-teal-border bg-accent-teal-soft px-2.5 py-0.5 font-mono text-[11px] font-semibold text-accent-teal">
                  Step {item.step}
                </span>
                <h3 className="mt-3 font-display text-sm font-semibold text-text-primary">
                  {item.title}
                </h3>
                <p className="mt-1.5 text-xs leading-relaxed text-text-secondary">
                  {item.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Band 3: Educational Pathology Reference Cards connecting back to Grad-CAM */}
      <section className="border-b border-border-subtle bg-bg-panel px-4 py-10 sm:px-6">
        <div className="mx-auto max-w-[1360px] space-y-5">
          <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
            <div>
              <h2 className="font-display text-lg font-bold text-text-primary">
                Thoracic Pattern Reference &amp; Differential Lookalikes
              </h2>
              <p className="text-xs text-text-secondary">
                Select any pattern below to focus Grad-CAM saliency inside the PACS Workstation.
              </p>
            </div>
            <Link
              to="/workstation"
              className="inline-flex items-center gap-1 text-xs font-semibold text-accent-brand hover:text-accent-brand-hover"
            >
              <span>Open PACS Workstation</span>
              <Eye className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Object.entries(PATHOLOGY_EVIDENCE_GUIDE)
              .slice(0, 4)
              .map(([name, info]) => (
                <div
                  key={name}
                  className="flex flex-col justify-between rounded-[var(--panel-radius)] border border-border-subtle bg-bg-canvas p-4"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-display text-sm font-semibold text-text-primary">
                        {name}
                      </h3>
                      <Activity className="h-3.5 w-3.5 text-accent-brand" aria-hidden="true" />
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-text-secondary">
                      {info.summary}
                    </p>
                    <p className="mt-2 text-[11px] leading-relaxed text-text-muted">
                      <strong className="font-semibold text-text-secondary">Key lookalikes:</strong>{' '}
                      {info.lookalikes}
                    </p>
                  </div>

                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-4 w-full"
                    onClick={() => {
                      void changePathologyHeatmap(name).then(() => navigate('/workstation'))
                    }}
                  >
                    <span>Focus on {name}</span>
                    <ArrowRight className="h-3 w-3" aria-hidden="true" />
                  </Button>
                </div>
              ))}
          </div>
        </div>
      </section>

      {/* Band 4: Responsible Scope & Compliance Notice Footer */}
      <footer className="bg-bg-canvas px-4 py-7 sm:px-6">
        <div className="mx-auto flex max-w-[1360px] flex-col gap-3 rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel p-4 text-xs text-text-secondary sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-accent-attention" aria-hidden="true" />
            <p className="max-w-3xl leading-relaxed">
              <strong className="font-semibold text-text-primary">Clinical Decision-Support Scope:</strong>{' '}
              AI probability estimates and Grad-CAM heatmaps assist radiologists with triage ordering only and do not constitute an autonomous medical diagnosis. All study storage complies with DICOM PS 3.15 Safe Harbor, AES-256-GCM envelope sealing, and India DPDP Act 2023 Sec. 12 right-to-erasure.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant="verified">HIPAA §164.514</Badge>
            <Badge variant="teal">DPDP Sec. 12</Badge>
          </div>
        </div>
      </footer>
    </div>
  )
}

