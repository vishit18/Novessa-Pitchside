import { CHROME_BUTTON } from '@/components/chromeStyles'
import { useCommentary } from '@/state/useCommentary'
import { useT } from '@/state/useSession'

/** Voice commentary on or off, for the broadcast view. */
export function CommentaryToggle() {
  const t = useT()
  const { on, toggle } = useCommentary()
  return (
    <button className={CHROME_BUTTON} aria-pressed={on} onClick={toggle}>
      {t(on ? 'commentaryOn' : 'commentaryOff')}
    </button>
  )
}
