import React from 'react'
import { cn } from '../../lib/utils'

interface SkeletonProps {
  className?: string
  lines?:     number
}

export function Skeleton({ className, lines }: SkeletonProps): React.ReactElement {
  if (lines && lines > 1) {
    return (
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={cn(
              'h-4 bg-slate-700/60 rounded animate-pulse',
              i === lines - 1 && 'w-3/4',
              className,
            )}
          />
        ))}
      </div>
    )
  }

  return (
    <div
      className={cn(
        'bg-slate-700/60 rounded animate-pulse',
        className,
      )}
    />
  )
}

export function SkeletonCard(): React.ReactElement {
  return (
    <div className="card-rune p-5 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <Skeleton lines={2} />
      <div className="flex gap-4">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-16" />
      </div>
      <div className="flex gap-2 pt-1">
        <Skeleton className="h-8 flex-1 rounded-md" />
        <Skeleton className="h-8 w-10 rounded-md" />
      </div>
    </div>
  )
}

export function SkeletonTable({ rows = 4 }: { rows?: number }): React.ReactElement {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 bg-slate-900/50 rounded-lg border border-slate-700/40">
          <Skeleton className="h-4 w-4 rounded-full shrink-0" />
          <div className="flex-1 space-y-1">
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-3 w-12 shrink-0" />
        </div>
      ))}
    </div>
  )
}
