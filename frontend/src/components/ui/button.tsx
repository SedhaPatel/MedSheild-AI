import type { ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-[var(--control-radius)] text-[13px] font-medium whitespace-nowrap transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-focus disabled:pointer-events-none disabled:opacity-45',
  {
    variants: {
      variant: {
        default:
          'border border-border-strong bg-bg-panel text-text-primary hover:bg-bg-elevated',
        primary:
          'border border-accent-brand bg-accent-brand text-text-inverse hover:border-accent-brand-hover hover:bg-accent-brand-hover',
        soft:
          'border border-border-strong bg-bg-panel text-accent-brand hover:bg-bg-elevated',
        ghost:
          'border border-transparent text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
        outline:
          'border border-border-subtle bg-bg-panel text-text-secondary hover:border-border-strong hover:bg-bg-elevated hover:text-text-primary',
        destructive:
          'border border-accent-critical bg-bg-panel text-accent-critical hover:bg-accent-critical hover:text-text-inverse',
      },
      size: {
        sm: 'h-7 px-2.5 text-xs',
        md: 'h-8 px-3 text-[13px]',
        lg: 'h-9 px-4 text-[13px]',
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
