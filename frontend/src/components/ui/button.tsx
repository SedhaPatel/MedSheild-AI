import type { ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-[var(--control-radius)] text-xs font-medium transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-focus active:scale-[0.97] disabled:pointer-events-none disabled:opacity-40',
  {
    variants: {
      variant: {
        default: 'border border-border-strong bg-bg-elevated text-text-primary hover:bg-bg-elevated/80',
        ghost: 'border border-transparent text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
        outline: 'border border-border-subtle bg-transparent text-text-secondary hover:border-border-strong hover:bg-bg-elevated hover:text-text-primary',
        destructive:
          'border border-accent-critical/30 bg-accent-critical/10 text-accent-critical hover:border-accent-critical/50 hover:bg-accent-critical/20',
      },
      size: {
        sm: 'h-7 px-2.5 text-[11px]',
        md: 'h-8 px-3 text-xs',
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

