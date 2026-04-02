import React, { type ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?:        string
  error?:        string
  helperText?:   string
  leftElement?:  ReactNode
  rightElement?: ReactNode
}

export function Input({
  label,
  error,
  helperText,
  leftElement,
  rightElement,
  id,
  className,
  ...rest
}: InputProps): React.ReactElement {
  const inputId   = id ?? label?.toLowerCase().replace(/\s+/g, '-')
  const descId    = error ? `${inputId}-error` : helperText ? `${inputId}-helper` : undefined

  return (
    <div className="space-y-1">
      {label && (
        <label htmlFor={inputId} className="label-rune">
          {label}
        </label>
      )}

      <div className="relative">
        {leftElement && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
            {leftElement}
          </div>
        )}

        <input
          id={inputId}
          aria-invalid={!!error}
          aria-describedby={descId}
          className={cn(
            'input-dark',
            leftElement  ? 'pl-9' : '',
            rightElement ? 'pr-9' : '',
            error ? 'border-red-600 focus:border-red-500' : '',
            className,
          )}
          {...rest}
        />

        {rightElement && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">
            {rightElement}
          </div>
        )}
      </div>

      {error && (
        <p id={`${inputId}-error`} className="text-xs text-red-400 mt-0.5">
          {error}
        </p>
      )}

      {!error && helperText && (
        <p id={`${inputId}-helper`} className="text-xs text-slate-500 mt-0.5">
          {helperText}
        </p>
      )}
    </div>
  )
}
