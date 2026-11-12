import {
  Contrast,
  Download,
  Hand,
  RotateCcw,
  SlidersHorizontal,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { getDicomDownloadUrl } from '@/lib/api'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

const PATHOLOGIES = [
  'Pneumonia',
  'Cardiomegaly',
  'Pleural Effusion',
  'Pneumothorax',
  'Atelectasis',
]

export function ViewportToolbar() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const viewMode = useWorkstationStore((s) => s.viewMode)
  const activeTool = useWorkstationStore((s) => s.activeTool)
  const targetPathology = useWorkstationStore((s) => s.targetPathology)
  const heatmapOpacity = useWorkstationStore((s) => s.heatmapOpacity)
  const isInverted = useWorkstationStore((s) => s.isInverted)

  const setActiveTool = useWorkstationStore((s) => s.setActiveTool)
  const changePathologyHeatmap = useWorkstationStore((s) => s.changePathologyHeatmap)
  const setHeatmapOpacity = useWorkstationStore((s) => s.setHeatmapOpacity)
  const toggleInvert = useWorkstationStore((s) => s.toggleInvert)
  const triggerZoomStep = useWorkstationStore((s) => s.triggerZoomStep)
  const triggerResetViewport = useWorkstationStore((s) => s.triggerResetViewport)

  if (!activeStudy) return null

  return (
    <TooltipProvider delayDuration={250}>
      <div
        className="absolute inset-x-0 bottom-0 z-10 flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle bg-bg-panel px-3 py-1.5"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Left group: Pathology Selector + Opacity Mix */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-text-muted">Heatmap for</span>
            <Select
              value={targetPathology}
              onValueChange={(val) => {
                void changePathologyHeatmap(val)
              }}
            >
              <SelectTrigger aria-label="Finding to show the heatmap for">
                <SelectValue placeholder="Pathology" />
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

          {viewMode === 'heatmap' && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted">Opacity</span>
              <Slider
                aria-label="Heatmap opacity"
                className="w-20"
                min={0}
                max={100}
                step={1}
                value={[heatmapOpacity]}
                onValueChange={([v]) => setHeatmapOpacity(v ?? 80)}
              />
              <span className="w-8 text-right font-mono text-[11px] text-text-muted tabular-nums">
                {heatmapOpacity}%
              </span>
            </div>
          )}
        </div>

        {/* Right group: Cornerstone3D PACS tools + Export */}
        <div className="flex items-center gap-1">
          {viewMode === 'redacted' && (
            <>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="sm"
                    variant={activeTool === 'WindowLevel' ? 'soft' : 'outline'}
                    onClick={() => setActiveTool('WindowLevel')}
                    aria-label="Window Level tool"
                  >
                    <SlidersHorizontal className="h-3.5 w-3.5" />
                    <span>W/L</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Window Width / Center drag</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="icon"
                    variant={activeTool === 'Pan' ? 'soft' : 'outline'}
                    onClick={() => setActiveTool('Pan')}
                    aria-label="Pan DICOM viewport"
                  >
                    <Hand className="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Pan image</TooltipContent>
              </Tooltip>
            </>
          )}

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="sm"
                variant={isInverted ? 'soft' : 'outline'}
                onClick={toggleInvert}
                aria-label="Invert radiograph grayscale"
              >
                <Contrast className="h-3.5 w-3.5" />
                <span>Invert</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Invert grayscale polarity [I]</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="outline"
                onClick={() => triggerZoomStep(1.18)}
                aria-label="Zoom in"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Zoom in [+]</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="outline"
                onClick={() => triggerZoomStep(0.85)}
                aria-label="Zoom out"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Zoom out [-]</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="outline"
                onClick={triggerResetViewport}
                aria-label="Reset camera and windowing"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Reset viewport [0]</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <a
                href={getDicomDownloadUrl(activeStudy.anonymous_study_instance_uid, true)}
                className="ml-1 inline-flex h-7 items-center gap-1 rounded-[var(--control-radius)] border border-border-strong bg-bg-panel px-2.5 text-xs font-medium text-text-primary transition-colors hover:bg-bg-elevated focus-visible:outline-2 focus-visible:outline-border-focus"
                aria-label="Download scrubbed Part 10 DICOM"
              >
                <Download className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Download .dcm</span>
              </a>
            </TooltipTrigger>
            <TooltipContent>Download the de-identified DICOM file</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </TooltipProvider>
  )
}

