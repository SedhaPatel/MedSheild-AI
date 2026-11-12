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
        className="absolute inset-x-3 bottom-3 z-10 flex flex-wrap items-center justify-between gap-2 rounded-[var(--control-radius)] border border-border-strong bg-bg-panel/95 px-3 py-1.5 backdrop-blur-xs transition-colors duration-150"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Left group: Pathology Selector + Opacity Mix */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-medium text-text-secondary">
              Target
            </span>
            <Select
              value={targetPathology}
              onValueChange={(val) => {
                void changePathologyHeatmap(val)
              }}
            >
              <SelectTrigger aria-label="Target pathology for Grad-CAM">
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
              <span className="text-[11px] font-medium text-text-secondary">
                Mix
              </span>
              <Slider
                aria-label="Grad-CAM overlay opacity"
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
                className="inline-flex h-7 items-center gap-1 rounded-[var(--control-radius)] border border-accent-brand-border bg-accent-brand-soft px-2.5 text-[11px] font-medium text-accent-brand-hover transition-colors hover:bg-accent-info-soft focus-visible:outline-2 focus-visible:outline-border-focus"
                aria-label="Download scrubbed Part 10 DICOM"
              >
                <Download className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">DICOM</span>
              </a>
            </TooltipTrigger>
            <TooltipContent>Download anonymized Part 10 .dcm</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </TooltipProvider>
  )
}

