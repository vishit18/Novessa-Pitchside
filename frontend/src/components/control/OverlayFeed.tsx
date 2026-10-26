import { useEffect, useMemo, useState } from 'react'
import { PLAYERS } from '@/data/league'
import { GATEWAY_HTTP } from '@/net/api'
import type { OverlayEnvelope } from '@/types/overlay'

const ROWS = 14
/** The slots a graphics operator cares about; tags and pitch marks stack on the feed itself. */
const SHOWN = new Set(['lower_third', 'player_tag', 'pitch_annotation'])

const PERSONA_NAME: Record<string, string> = {
  analyst: 'Analyst',
  casual: 'Casual',
  kids: 'First match',
  accessibility: 'Audio-described',
}

/** Who a cue goes to: one variant of a state of play is for analysts, the other for everyone else. */
function audience(o: OverlayEnvelope): string {
  if (o.persona.length >= 4) return 'everyone'
  return o.persona.map((p) => PERSONA_NAME[p] ?? p).join(', ')
}

const mmss = (t: number) =>
  `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(Math.floor(t % 60)).padStart(2, '0')}`

/** The words a cue carries, for the row: a headline, a name and a speed, a pass. */
function cueText(o: OverlayEnvelope): string {
  const p = o.payload
  if (typeof p['headline'] === 'string') return String(p['headline'])
  const who = PLAYERS[String(p['player_id'] ?? '')]?.name ?? ''
  if (o.kind === 'speed_burst') return `${who}, ${Number(p['speed_kmh']).toFixed(1)} km/h`
  if (o.kind === 'pass_difficulty') return `${who}, difficulty ${p['difficulty']}`
  if (o.kind === 'distance_milestone') return `${who}, ${p['km']} km`
  if (o.kind === 'shot_speed') return `${who}, ${Number(p['speed_kmh']).toFixed(0)} km/h shot`
  return o.kind.replace(/_/g, ' ')
}

/**
 * What a graphics engine receives: the overlay protocol as timed cues, newest first, as far as
 * the viewer has watched. Pick a cue to see the exact message beside the plate it draws. This is
 * the production path the brief describes; our own broadcast view is just one renderer of it.
 */
export function OverlayFeed({ matchId, upto }: { matchId: string; upto: number | null }) {
  const [all, setAll] = useState<OverlayEnvelope[] | null>(null)
  const [pick, setPick] = useState<string | null>(null)
  const query = upto === null ? '' : `?upto=${Math.floor(upto)}`

  useEffect(() => {
    let live = true
    fetch(`${GATEWAY_HTTP}/matches/${encodeURIComponent(matchId)}/overlays.jsonl${query}`)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((text) => {
        if (!live) return
        const rows = text
          .split('\n')
          .filter(Boolean)
          .map((l) => JSON.parse(l) as OverlayEnvelope)
        setAll(rows)
      })
      .catch(() => live && setAll([]))
    return () => {
      live = false
    }
  }, [matchId, query])

  const cues = useMemo(
    () =>
      (all ?? [])
        .filter((o) => SHOWN.has(o.slot))
        .slice(-ROWS)
        .reverse(),
    [all],
  )
  const chosen = cues.find((o) => o.msg_id === pick) ?? cues[0] ?? null

  return (
    <section aria-labelledby="feed-h" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 id="feed-h" className="font-display text-[26px] font-semibold leading-none">
          What the graphics engine receives
        </h2>
        <p className="flex gap-4 text-[14px]">
          <a
            className="text-amber underline underline-offset-4"
            href={`${GATEWAY_HTTP}/matches/${encodeURIComponent(matchId)}/overlays.jsonl${query}`}
          >
            Overlay feed (JSONL)
          </a>
          <a
            className="text-amber underline underline-offset-4"
            href={`${GATEWAY_HTTP}/matches/${encodeURIComponent(matchId)}/cues.csv`}
          >
            Cue sheet (CSV)
          </a>
        </p>
      </div>
      <p className="max-w-[80ch] text-[14px] leading-relaxed text-muted">
        Every graphic is a timed message keyed to match time, so a renderer on a 30-second delay
        still lands it on the right second. Our broadcast view is one renderer; a studio graphics
        system could be another.
      </p>
      {all === null ? (
        <p className="pulse-soft text-[14px] text-muted">Loading the feed</p>
      ) : cues.length === 0 ? (
        <p className="text-[14px] text-muted">No cues yet. Watch some of the match first.</p>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <ol className="flex flex-col divide-y divide-hairline border-y border-hairline">
            {cues.map((o) => (
              <li key={o.msg_id}>
                <button
                  onClick={() => setPick(o.msg_id)}
                  aria-pressed={chosen?.msg_id === o.msg_id}
                  className="grid w-full grid-cols-[3.5rem_7.5rem_1fr_auto] items-baseline gap-3 px-2 py-2 text-start hover:bg-raised aria-pressed:bg-raised"
                >
                  <span className="num text-[16px] text-amber" dir="ltr">
                    {mmss(o.show_at)}
                  </span>
                  <span className="truncate text-[13px] text-muted">
                    {o.slot.replace('_', ' ')}
                  </span>
                  <span className="truncate text-[15px]">{cueText(o)}</span>
                  <span className="truncate text-[13px] text-muted">{audience(o)}</span>
                </button>
              </li>
            ))}
          </ol>
          {chosen && (
            <div className="flex min-w-0 flex-col gap-3">
              <Preview o={chosen} />
              <pre
                // Scrollable, so a keyboard user has to be able to reach it.
                tabIndex={0}
                className="max-h-[340px] overflow-auto border border-hairline bg-raised p-3 text-[12px] leading-snug"
                dir="ltr"
                aria-label="The overlay message"
              >
                {JSON.stringify(chosen, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

/** The plate this message draws, in the broadcast's own style, so data and picture sit together. */
function Preview({ o }: { o: OverlayEnvelope }) {
  const p = o.payload
  const head = typeof p['headline'] === 'string' ? String(p['headline']) : cueText(o)
  const body = typeof p['body'] === 'string' ? String(p['body']) : null
  return (
    <div className="stage-bg p-4">
      <p className="mb-2 text-[12px] text-muted">
        Renders as: {o.slot.replace('_', ' ')}, for {mmss(o.duration_s)} from{' '}
        <span className="num">{mmss(o.show_at)}</span>
      </p>
      <div className="plate-shadow w-fit max-w-full">
        <div className="plate flex" style={{ ['--cut' as string]: '12px' }}>
          <span className="plate-edge w-[6px] shrink-0 bg-amber" />
          <div className="min-w-0 py-2 pe-6 ps-3">
            <p className="font-display text-[22px] font-bold leading-none">{head}</p>
            {body && <p className="mt-1 line-clamp-2 text-[14px] text-text/80">{body}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
