import {
  init as csRenderInit,
  setUseCPURendering,
  isCornerstoneInitialized,
} from '@cornerstonejs/core'
import {
  init as csToolsInit,
  addTool,
  WindowLevelTool,
  PanTool,
  ZoomTool,
  ToolGroupManager,
  Enums as csToolsEnums,
} from '@cornerstonejs/tools'
import dicomImageLoader from '@cornerstonejs/dicom-image-loader'
import type { PACSActiveTool } from '@/types/clinical'

export const WORKSTATION_TOOL_GROUP_ID = 'medshield-pacs-tool-group'
export const WORKSTATION_RENDERING_ENGINE_ID = 'medshield-pacs-engine'
export const WORKSTATION_VIEWPORT_ID = 'medshield-pacs-stack'

let bootPromise: Promise<void> | null = null

function hasWebGL2Support(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(window.WebGL2RenderingContext && canvas.getContext('webgl2'))
  } catch {
    return false
  }
}

export async function ensureCornerstoneReady(): Promise<void> {
  if (bootPromise) return bootPromise

  bootPromise = (async () => {
    if (!isCornerstoneInitialized()) {
      if (!hasWebGL2Support()) {
        setUseCPURendering(true)
      }
      csRenderInit()
      csToolsInit()
      dicomImageLoader.init({
        maxWebWorkers: Math.min(2, navigator.hardwareConcurrency || 1),
        useLegacyMetadataProvider: true,
      })
    }

    try {
      addTool(WindowLevelTool)
      addTool(PanTool)
      addTool(ZoomTool)
    } catch {
      // Ignore duplicate registration across StrictMode remounts
    }

    let toolGroup = ToolGroupManager.getToolGroup(WORKSTATION_TOOL_GROUP_ID)
    if (!toolGroup) {
      toolGroup = ToolGroupManager.createToolGroup(WORKSTATION_TOOL_GROUP_ID)
    }

    if (toolGroup) {
      toolGroup.addTool(WindowLevelTool.toolName)
      toolGroup.addTool(PanTool.toolName)
      toolGroup.addTool(ZoomTool.toolName)

      toolGroup.setToolActive(WindowLevelTool.toolName, {
        bindings: [{ mouseButton: csToolsEnums.MouseBindings.Primary }],
      })
      toolGroup.setToolActive(PanTool.toolName, {
        bindings: [{ mouseButton: csToolsEnums.MouseBindings.Auxiliary }],
      })
      toolGroup.setToolActive(ZoomTool.toolName, {
        bindings: [{ mouseButton: csToolsEnums.MouseBindings.Secondary }],
      })
    }
  })()

  return bootPromise
}

export function setPrimaryMouseTool(activeTool: PACSActiveTool): void {
  const toolGroup = ToolGroupManager.getToolGroup(WORKSTATION_TOOL_GROUP_ID)
  if (!toolGroup) return

  const toolNames: Record<PACSActiveTool, string> = {
    WindowLevel: WindowLevelTool.toolName,
    Pan: PanTool.toolName,
    Zoom: ZoomTool.toolName,
  }

  Object.values(toolNames).forEach((name) => {
    toolGroup.setToolPassive(name)
  })

  toolGroup.setToolActive(toolNames[activeTool], {
    bindings: [{ mouseButton: csToolsEnums.MouseBindings.Primary }],
  })

  if (activeTool !== 'Pan') {
    toolGroup.setToolActive(PanTool.toolName, {
      bindings: [{ mouseButton: csToolsEnums.MouseBindings.Auxiliary }],
    })
  }
  if (activeTool !== 'Zoom') {
    toolGroup.setToolActive(ZoomTool.toolName, {
      bindings: [{ mouseButton: csToolsEnums.MouseBindings.Secondary }],
    })
  }
}

