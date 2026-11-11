import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-[var(--control-radius)] border px-2 py-0.5 text-[11px] font-medium leading-tight whitespace-nowrap transition-colors',
  {
    variants: {
      variant: {
        verified: 'border-accent-verified/25 bg-accent-verified/10 text-accent-verified',
        attention: 'border-accent-attention/25 bg-accent-attention/10 text-accent-attention',
        critical: 'border-accent-critical/25 bg-accent-critical/10 text-accent-critical',
        info: 'border-accent-info/25 bg-accent-info/10 text-accent-info',
        neutral: 'border-border-subtle bg-bg-elevated text-text-secondary',
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

