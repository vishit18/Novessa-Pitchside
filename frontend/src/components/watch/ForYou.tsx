import { CLUBS, PLAYERS } from '@/data/league'
import { useSessionState, useT } from '@/state/useSession'

/** Minutes in normal time; past this the "minutes left" line drops. */
const FULL_TIME = 90

/**
 * Who this broadcast is for, said in the viewer's terms: their side and where it stands, or
 * their player, or an invitation to pick a side. Always on screen beside the match, so the
 * personal part of the broadcast is never hidden in a settings page.
 */
export function ForYou({ onPick }: { onPick: () => void }) {
  const t = useT()
  const profile = useSessionState((s) => s.profile)
  const meta = useSessionState((s) => s.meta)
  const snap = useSessionState((s) => s.snapshot)
  if (!meta) return null

  if (!profile.club && !profile.player) {
    return (
      <div className="flex items-center justify-between gap-4 border-s-4 border-hairline ps-3">
        <p className="text-[15px] leading-snug text-text/80">{t('forYouNone')}</p>
        <button
          onClick={onPick}
          className="h-10 shrink-0 border border-text px-3 text-[14px] font-semibold hover:border-amber hover:text-amber"
        >
          {t('pickSide')}
        </button>
      </div>
    )
  }

  const club = profile.club ?? (profile.player ? profile.player.split('-')[0]! : null)
  const other = club === meta.home.code ? meta.away.code : meta.home.code
  const mine = club ? (snap?.score[club] ?? 0) : 0
  const theirs = snap?.score[other] ?? 0
  const score = `${mine}–${theirs}`
  const minute = snap ? Number(snap.clock.split(':')[0]) : 0
  const left = FULL_TIME - minute
  const line =
    mine > theirs
      ? t('youLead', { score })
      : mine < theirs
        ? t('youTrail', { score })
        : t('youLevel', { score })
  const kit = club ? (CLUBS[club]?.primary_color ?? '#9aa5b1') : '#9aa5b1'
  const player = profile.player ? PLAYERS[profile.player] : null

  return (
    <div className="flex items-stretch gap-3">
      <span className="w-[5px] shrink-0" style={{ background: kit }} aria-hidden />
      <div className="min-w-0">
        <p className="text-[14px] text-muted">
          {player
            ? t('youFollow', { name: player.name })
            : t('youWith', { club: CLUBS[club ?? '']?.name ?? club ?? '' })}
        </p>
        <p className="mt-0.5 font-display text-[28px] font-bold leading-none">
          {line}
          {snap && snap.period === 2 && left > 0 && mine !== theirs && (
            <span className="ms-2 text-[17px] font-semibold text-muted">
              {t('minutesLeft', { n: left })}
            </span>
          )}
        </p>
      </div>
    </div>
  )
}
