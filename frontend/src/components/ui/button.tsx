import type { ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-[var(--control-radius)] text-xs font-medium transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-focus active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45',
  {
    variants: {
      variant: {
        default:
          'border border-border-strong bg-bg-panel text-text-primary hover:bg-bg-elevated',
        primary:
          'border border-accent-brand bg-accent-brand text-text-inverse hover:border-accent-brand-hover hover:bg-accent-brand-hover',
        soft:
          'border border-accent-brand-border bg-accent-brand-soft text-accent-brand-hover hover:bg-accent-info-soft',
        ghost:
          'border border-transparent text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
        outline:
          'border border-border-subtle bg-bg-panel text-text-secondary hover:border-border-strong hover:bg-bg-elevated hover:text-text-primary',
        destructive:
          'border border-accent-critical-border bg-accent-critical-soft text-accent-critical hover:border-accent-critical hover:bg-accent-critical hover:text-text-inverse',
      },
      size: {
        sm: 'h-7 px-2.5 text-[11px]',
        md: 'h-8 px-3.5 text-xs',
        lg: 'h-9 px-4 text-xs',
        icon: 'h-7 w-7 p-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  }
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}
