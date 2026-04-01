import React, { type ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface BadgeProps {
  variant?:   'default' | 'success' | 'warning' | 'danger' | 'info' | 'condition'
  children:   ReactNode
  className?: string
}

const VARIANT_CLASSES: Record<NonNullable<BadgeProps['variant']>, string> = {
  default:   'badge',
  success:   'badge badge-success',
  warning:   'badge badge-warning',
  danger:    'badge badge-error',
  info:      'badge badge-info',
  condition: 'badge badge-condition',
}

export function Badge({
  variant = 'default',
  children,
  className,
}: BadgeProps): React.ReactElement {
  return (
    <span className={cn(VARIANT_CLASSES[variant], className)}>
      {children}
    </span>
  )
}
