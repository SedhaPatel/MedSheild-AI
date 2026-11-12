export type TriageUrgency = 'STAT_CRITICAL' | 'ELEVATED' | 'ROUTINE'
export type ViewPlaneMode = 'raw' | 'redacted' | 'heatmap'
export type PACSActiveTool = 'WindowLevel' | 'Pan' | 'Zoom'

export interface SampleCase {
  id: string
  name: string
  modality: string
  finding: string
  urgency: TriageUrgency
  dcm_path: string
  png_path: string
}

export interface PredictionItem {
  pathology: string
  probability: number
  epistemic_uncertainty: number
  triage_urgency: TriageUrgency
  gradcam_heatmap_url: string | null
  bounding_box_normalized: number[] | null
}

export interface PiiTagDiff {
  tag_hex: string
  tag_name: string
  description: string
  original_value: string
  sanitized_value: string
  status: 'SANITIZED' | 'UNALTERED' | 'MODIFIED'
}

export interface SecurityMetrics {
  encryption_algorithm: string
  container_magic_header: string
  kms_master_key_id: string
  storage_file_path: string
  storage_file_size_bytes: number
  sha256_hash: string
  shannon_entropy_bits_per_byte: number
  entropy_target: string
  hex_preview_64b: string
  is_tamper_resistant: boolean
  dpdp_crypto_shredding_ready: boolean
}

export interface DeidentificationSummary {
  burned_in_text_redacted: boolean
  safe_harbor_compliance: string
  uid_root: string
  tag_diff_matrix: PiiTagDiff[]
}

export interface AIDiagnosticsSummary {
  model_name: string
  is_real_weights: boolean
  weights_source: string
  inference_latency_ms: number
  overall_triage_urgency: TriageUrgency
  active_heatmap_pathology: string
  predictions: PredictionItem[]
}

export interface StudyAnalysisResponse {
  status: string
  file_name: string
  anonymous_study_instance_uid: string
  dicom_url: string
  security: SecurityMetrics
  deidentification: DeidentificationSummary
  ai_diagnostics: AIDiagnosticsSummary
  images: {
    raw_image_url: string
    redacted_image_url: string
    gradcam_heatmap_url: string
  }
  worklist?: WorklistEntry[]
}

export interface WorklistEntry {
  anonymous_study_instance_uid: string
  file_name: string
  modality: string
  overall_triage_urgency: TriageUrgency
  top_pathology: string
  top_probability: number
  shannon_entropy: number
  is_shredded: boolean
  ingested_at_utc: string
}

export interface ShredResponse {
  status: string
  study_uid: string
  revoked_kek_id: string
  math_erasure_verified: boolean
  legal_standard: string
  message: string
  worklist?: WorklistEntry[]
}

export interface ScanChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface ScanChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  provider_used?: string
  grounded_findings?: string[]
  timestamp: number
  isError?: boolean
}

export interface ScanChatRequest {
  scan_id: string
  user_message: string
  target_pathology?: string
  include_heatmap_overlay?: boolean
  conversation_history?: ScanChatTurn[]
}

export interface ScanChatResponse {
  scan_id: string
  provider_used: string
  answer: string
  grounded_findings: string[]
  zero_pii_verified: boolean
  pii_redacted_from_prompt: boolean
  medical_disclaimer: string
}


