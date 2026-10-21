/** The few drawn marks the app uses, in one stroke weight. Size and colour come from the parent. */

export function CheckIcon({ className = 'size-3' }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={`inline-block shrink-0 ${className}`} aria-hidden>
      <path d="M2 6.5 5 9l5-6" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  )
}

export function CrossIcon({ className = 'size-3' }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={`inline-block shrink-0 ${className}`} aria-hidden>
      <path d="M2.5 2.5l7 7M9.5 2.5l-7 7" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  )
}

export function DashIcon({ className = 'size-3' }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={`inline-block shrink-0 ${className}`} aria-hidden>
      <path d="M2.5 6h7" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  )
}

export function AlertIcon({ className = 'size-3' }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={`inline-block shrink-0 ${className}`} aria-hidden>
      <path d="M6 1.5v6M6 9.5v1" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  )
}

export function ChevronDownIcon({ className = 'size-3' }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={`inline-block shrink-0 ${className}`} aria-hidden>
      <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}
