import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useWorkstationStore } from '@/stores/useWorkstationStore'
import type { ViewPlaneMode } from '@/types/clinical'

const TAB_HINT: Record<ViewPlaneMode, string> = {
  raw: 'As uploaded, before de-identification',
  redacted: 'Stored DICOM after de-identification',
  heatmap: 'Regions that most influenced the selected finding',
}

export function ViewerTabs() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const viewMode = useWorkstationStore((s) => s.viewMode)
  const setViewMode = useWorkstationStore((s) => s.setViewMode)

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle bg-bg-panel pr-4 pl-3">
      <Tabs value={viewMode} onValueChange={(val) => setViewMode(val as ViewPlaneMode)}>
        <TabsList aria-label="Image view">
          <TabsTrigger value="raw">Original</TabsTrigger>
          <TabsTrigger value="redacted">De-identified</TabsTrigger>
          <TabsTrigger value="heatmap">Heatmap</TabsTrigger>
        </TabsList>
      </Tabs>
      {activeStudy && (
        <span className="hidden text-xs text-text-muted md:inline">
          {viewMode === 'heatmap'
            ? `${TAB_HINT.heatmap}: ${activeStudy.ai_diagnostics.active_heatmap_pathology}`
            : TAB_HINT[viewMode]}
        </span>
      )}
    </div>
  )
}
