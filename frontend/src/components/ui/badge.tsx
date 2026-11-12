import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-[3px] border px-1.5 py-px text-[11px] font-medium leading-4 whitespace-nowrap',
  {
    variants: {
      variant: {
        verified:
          'border-accent-verified-border bg-accent-verified-soft text-accent-verified',
        attention:
          'border-accent-attention-border bg-accent-attention-soft text-accent-attention',
        critical:
          'border-accent-critical-border bg-accent-critical-soft text-accent-critical',
        info:
          'border-accent-info-border bg-accent-info-soft text-accent-info',
        teal:
          'border-accent-teal-border bg-accent-teal-soft text-accent-teal',
        neutral:
          'border-border-subtle bg-bg-elevated text-text-secondary',
      },
    },
    defaultVariants: {
      variant: 'neutral',
    },
  }
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
