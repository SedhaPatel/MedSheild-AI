import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '@/lib/utils'

export const TooltipProvider = TooltipPrimitive.Provider
export const Tooltip = TooltipPrimitive.Root
export const TooltipTrigger = TooltipPrimitive.Trigger

export function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          'z-50 shadow-[0_4px_16px_rgba(16,24,40,0.10)] rounded-[var(--viewport-radius)] border border-border-strong bg-bg-panel px-2.5 py-1 text-[11px] font-medium text-text-primary',
          className
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  )
}
