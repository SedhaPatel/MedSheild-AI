import * as SliderPrimitive from '@radix-ui/react-slider'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '@/lib/utils'

export function Slider({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof SliderPrimitive.Root>) {
  return (
    <SliderPrimitive.Root
      className={cn('relative flex w-full touch-none select-none items-center cursor-pointer', className)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-border-subtle">
        <SliderPrimitive.Range className="absolute h-full bg-accent-brand" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb className="block h-3.5 w-3.5 rounded-full border-2 border-accent-brand bg-bg-panel transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-focus" />
    </SliderPrimitive.Root>
  )
}
