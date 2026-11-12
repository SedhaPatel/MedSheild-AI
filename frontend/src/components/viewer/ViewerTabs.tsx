import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { useWorkstationStore } from '@/stores/useWorkstationStore'
import type { ViewPlaneMode } from '@/types/clinical'

export function ViewerTabs() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const viewMode = useWorkstationStore((s) => s.viewMode)
  const setViewMode = useWorkstationStore((s) => s.setViewMode)

  const urgency = activeStudy?.ai_diagnostics.overall_triage_urgency
  const badgeVariant =
    urgency === 'STAT_CRITICAL'
      ? 'critical'
      : urgency === 'ELEVATED'
        ? 'attention'
        : 'verified'

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle bg-bg-panel pr-4 pl-2">
      <Tabs
        value={viewMode}
        onValueChange={(val) => setViewMode(val as ViewPlaneMode)}
      >
        <TabsList aria-label="Radiograph display plane">
          <TabsTrigger value="raw">Original [1]</TabsTrigger>
          <TabsTrigger value="redacted">De-Identified DICOM [2]</TabsTrigger>
          <TabsTrigger value="heatmap">Grad-CAM [3]</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="flex items-center gap-2">
        {activeStudy && (
          <>
            <span className="hidden text-[11px] text-text-muted md:inline">
              {viewMode === 'redacted'
                ? 'Left-drag: Window/Level • Right-drag: Zoom'
                : viewMode === 'heatmap'
                  ? 'Grad-CAM overlay aligned to lung anatomy'
                  : 'Pre-ingestion raw scan with original PHI'}
            </span>
            <Badge variant={badgeVariant}>
              {urgency?.replace('_', ' ')}
            </Badge>
          </>
        )}
      </div>
    </div>
  )
}

