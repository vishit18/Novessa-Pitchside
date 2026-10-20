import { useCommentary } from '@/state/useCommentary'
import { useT } from '@/state/useSession'

/** Voice commentary on or off, for the broadcast view. */
export function CommentaryToggle() {
  const t = useT()
  const { on, toggle } = useCommentary()
  return (
    <button
      className="-my-2 inline-flex min-h-11 items-center px-1 text-[14px] text-muted underline decoration-white/25 underline-offset-4 hover:text-text aria-pressed:text-amber"
      aria-pressed={on}
      onClick={toggle}
    >
      {t(on ? 'commentaryOn' : 'commentaryOff')}
    </button>
  )
}
