/** Reference descriptions of what each finding typically looks like (general radiology, not this image). */
export const PATHOLOGY_GUIDE: Record<string, { looksLike: string; lookalikes: string }> = {
  Pneumonia: {
    looksLike: 'Focal or lobar airspace opacity; may show air bronchograms or blur the diaphragm outline.',
    lookalikes: 'Atelectasis, pulmonary edema, overlapping pleural effusion.',
  },
  Cardiomegaly: {
    looksLike: 'Heart shadow wider than half the internal chest width on a PA view.',
    lookalikes: 'Magnification on AP views, pericardial effusion, elevated diaphragm.',
  },
  'Pleural Effusion': {
    looksLike: 'Fluid density blunting the costophrenic angle, often with a curved meniscus.',
    lookalikes: 'Pleural thickening, elevated hemidiaphragm, lower-lobe consolidation.',
  },
  Pneumothorax: {
    looksLike: 'Thin white pleural line with no lung markings beyond it.',
    lookalikes: 'Skin folds on bedside AP films, apical bullae, scapular edge.',
  },
  Atelectasis: {
    looksLike: 'Linear or plate-like density with signs of volume loss.',
    lookalikes: 'Scarring, subsegmental consolidation, hypoventilation.',
  },
}
