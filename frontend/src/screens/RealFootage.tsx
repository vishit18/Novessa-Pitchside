import { useEffect, useRef, useState } from 'react'
import { Wordmark } from '@/components/Hud'
import {
  activeBursts,
  activePasses,
  boxesAt,
  foot,
  passLine,
  trackOf,
  type Box,
  type RealOverlay,
} from '@/core/real'
import { navigate, withParams } from '@/router'
import { getOverlay, listClips, videoUrl, type RealClip } from '@/net/real'

const TEAM_COLOUR = { BLU: '#4d8dff', WHT: '#eef2f6' } as const
const AMBER = '#ffb020'

interface Layers {
  tags: boolean
  passes: boolean
  speeds: boolean
}

/**
 * Real footage mode. A model found every tag, speed and pass on this screen from the pixels of
 * a real match; none of it comes from the synthetic engine. Credit and licence stay on screen.
 */
export function RealFootage() {
  const [clip, setClip] = useState<RealClip | null>(null)
  const [overlay, setOverlay] = useState<RealOverlay | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    listClips()
      .then(async (all) => {
        const first = all[0]
        if (!first) throw new Error('no clips')
        const o = await getOverlay(first.clip)
        if (live) {
          setClip(first)
          setOverlay(o)
        }
      })
      .catch(() => live && setFailed(true))
    return () => {
      live = false
    }
  }, [])

  return (
    <main className="stage-bg mx-auto flex min-h-dvh w-full max-w-[1500px] flex-col gap-6 px-4 py-5 sm:px-8">
      <header className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
        <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
          <Wordmark />
          <h1 className="font-display text-[26px] font-semibold leading-none">Real footage</h1>
        </div>
        <button
          className="inline-flex min-h-11 items-center text-[14px] text-muted underline decoration-white/25 underline-offset-4 hover:text-text"
          onClick={() => navigate(withParams('/'))}
        >
          Back to the match
        </button>
      </header>

      {failed && (
        <p role="alert" className="max-w-[60ch] text-[15px]">
          The real footage did not load. The gateway may still be starting, so try again in a few
          seconds.
        </p>
      )}
      {!failed && !overlay && (
        <p role="status" className="pulse-soft text-[15px] text-muted">
          Loading the clip
        </p>
      )}
      {clip && overlay && <Player clip={clip} overlay={overlay} />}
    </main>
  )
}

function Player({ clip, overlay }: { clip: RealClip; overlay: RealOverlay }) {
  const video = useRef<HTMLVideoElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const [layers, setLayers] = useState<Layers>({ tags: true, passes: true, speeds: true })
  const layersRef = useRef(layers)
  useEffect(() => {
    layersRef.current = layers
  })

  useEffect(() => {
    let raf = 0
    const loop = () => {
      const v = video.current
      const c = canvas.current
      if (v && c) draw(c, v, overlay, layersRef.current)
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [overlay])

  const passes = overlay.events.filter((e) => e.type === 'pass' && e.outcome === 'complete')
  const seek = (t: number) => {
    const v = video.current
    if (v) {
      v.currentTime = Math.max(0, t - 1)
      void v.play().catch(() => undefined)
    }
  }
  const toggle = (k: keyof Layers) => setLayers((l) => ({ ...l, [k]: !l[k] }))

  return (
    <>
      <p className="max-w-[70ch] text-[15px] leading-relaxed text-muted">
        A real university match, filmed from one fixed camera. A model found every player, the ball,
        each pass and each sprint from the pixels. Nothing here is hand-tagged.
      </p>

      <section aria-label="Match video" className="flex flex-col gap-3">
        <div className="overflow-x-auto">
          <div className="relative min-w-[900px]">
            {clip.video ? (
              <video
                ref={video}
                src={videoUrl(clip.clip)}
                controls
                muted
                playsInline
                preload="auto"
                className="block w-full bg-black"
                style={{ aspectRatio: `${overlay.clip[0]} / ${overlay.clip[1]}` }}
              />
            ) : (
              <div
                className="grid w-full place-items-center bg-black/60 p-6 text-center text-[15px]"
                style={{ aspectRatio: `${overlay.clip[0]} / ${overlay.clip[1]}` }}
              >
                The video is not on this server, so only the findings are shown below.
              </div>
            )}
            <canvas
              ref={canvas}
              aria-hidden
              className="pointer-events-none absolute inset-0 size-full"
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          <div className="flex flex-wrap gap-1" role="group" aria-label="Show on the video">
            {(
              [
                ['tags', 'Player tags'],
                ['passes', 'Passes'],
                ['speeds', 'Sprint speeds'],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                aria-pressed={layers[k]}
                onClick={() => toggle(k)}
                className={`h-9 border px-3 text-[14px] font-medium ${
                  layers[k]
                    ? 'border-amber text-amber'
                    : 'border-white/30 text-muted hover:text-text'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="text-[13px] text-muted">
            {overlay.credit}. Marks painted on the pitch are removed.
          </p>
        </div>
      </section>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_520px] lg:gap-14">
        <section aria-labelledby="found-h" className="flex flex-col gap-3">
          <h2 id="found-h" className="font-display text-[26px] font-semibold leading-none">
            Passes it found
          </h2>
          <ol className="flex flex-col divide-y divide-white/10 border-y border-white/10">
            {passes.map((e) => (
              <li key={e.t_match + (e.player_id ?? '')}>
                <button
                  className="grid w-full grid-cols-[4.5rem_1fr] gap-x-3 px-1 py-3 text-start hover:bg-white/[0.03]"
                  onClick={() => seek(e.t_match)}
                >
                  <span className="num text-[22px] leading-none text-amber">{e.clock}</span>
                  <span>
                    <span className="block text-[15px]">
                      {overlay.tracks[String(trackOf(e.player_id))]?.label ?? e.player_id} to{' '}
                      {overlay.tracks[String(trackOf(e.receiver_id))]?.label ?? e.receiver_id}
                    </span>
                    <span className="block text-[13px] text-muted">{passLine(e)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>
        <Validation clip={clip} />
      </div>
    </>
  )
}

function pct(v: number) {
  return `${Math.round(v * 100)}%`
}

/** The validation numbers, with the weak one stated as plainly as the strong ones. */
function Validation({ clip }: { clip: RealClip }) {
  const r = clip.results
  const rows: [string, string, string][] = [
    [
      'Players found',
      pct(r.positions.recall),
      `${r.positions.matched.toLocaleString('en')} of ${r.positions.gt_players.toLocaleString('en')} labelled positions`,
    ],
    [
      'Position error',
      `${r.positions.median_error_m.toFixed(1)} m`,
      `typical; 9 in 10 within ${r.positions.p90_error_m.toFixed(1)} m`,
    ],
    [
      'Player speed error',
      `${r.speed.median_abs_error_kmh.toFixed(1)} km/h`,
      `typical; top speed ${r.speed.top_speed_error_kmh >= 0 ? '+' : ''}${r.speed.top_speed_error_kmh.toFixed(0)} km/h`,
    ],
    [
      'Passes found',
      `${r.passes.matched} of ${r.passes.gt}`,
      `${pct(r.passes.precision)} of the ones it reported were real`,
    ],
    ['Ball followed', pct(r.ball_found_fraction), 'of frames'],
  ]
  return (
    <section aria-labelledby="valid-h" className="flex flex-col gap-4">
      <h2 id="valid-h" className="font-display text-[26px] font-semibold leading-none">
        How good is it?
      </h2>
      <p className="text-[14px] leading-relaxed text-muted">
        Scored against the dataset’s own labels, which the model never saw. Players are easy to
        find. A ball about ten pixels wide in a 4K panorama is not, so passes are the weak spot.
      </p>
      <dl className="flex flex-col gap-3.5">
        {rows.map(([k, v, note]) => (
          <div key={k} className="grid grid-cols-[1fr_auto] items-baseline gap-x-4">
            <dt className="text-[14px]">
              {k}
              <span className="block text-[12px] text-muted">{note}</span>
            </dt>
            <dd className="num m-0 text-[26px] leading-none">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

/** Draw the current frame's overlay on the canvas that sits over the video. */
function draw(c: HTMLCanvasElement, v: HTMLVideoElement, o: RealOverlay, layers: Layers) {
  const dpr = window.devicePixelRatio || 1
  const w = c.clientWidth
  const h = c.clientHeight
  if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
    c.width = Math.round(w * dpr)
    c.height = Math.round(h * dpr)
  }
  const g = c.getContext('2d')
  if (!g) return
  g.setTransform(dpr, 0, 0, dpr, 0, 0)
  g.clearRect(0, 0, w, h)
  const s = w / o.clip[0]
  const t = v.currentTime
  const { boxes, ball } = boxesAt(o, t)
  const byId = new Map<number, Box>(boxes.map((b) => [b.id, b]))
  const passes = layers.passes ? activePasses(o.events, t) : []
  const bursts = layers.speeds ? activeBursts(o, t) : []
  const named = new Set<number>(
    [
      ...passes.flatMap((e) => [trackOf(e.player_id), trackOf(e.receiver_id)]),
      ...bursts.map((b) => b.track),
    ].filter((x): x is number => x != null),
  )

  g.font = `600 ${Math.max(10, 12 * Math.min(1, s + 0.4))}px "Barlow Condensed", sans-serif`
  g.textBaseline = 'bottom'
  if (layers.tags) {
    for (const b of boxes) {
      const team = o.tracks[String(b.id)]?.team ?? 'WHT'
      const col = TEAM_COLOUR[team]
      g.strokeStyle = col
      g.globalAlpha = 0.8
      g.lineWidth = 1.2
      g.strokeRect(b.x1 * s, b.y1 * s, (b.x2 - b.x1) * s, (b.y2 - b.y1) * s)
      g.globalAlpha = 1
      chip(g, String(b.id), b.x1 * s, b.y1 * s - 2, col)
    }
  }
  for (const id of named) {
    const b = byId.get(id)
    if (!b) continue
    const label = o.tracks[String(id)]?.label ?? String(id)
    const burst = bursts.find((x) => x.track === id)
    chip(
      g,
      burst ? `${label}  ${Math.round(burst.kmh)} km/h` : label,
      b.x1 * s,
      b.y1 * s - 16,
      AMBER,
      true,
    )
  }
  for (const e of passes) {
    const a = byId.get(trackOf(e.player_id) ?? -1)
    const r = byId.get(trackOf(e.receiver_id) ?? -1)
    if (!a || !r) continue
    const [ax, ay] = foot(a)
    const [rx, ry] = foot(r)
    g.strokeStyle = AMBER
    g.lineWidth = 2.5
    g.beginPath()
    g.moveTo(ax * s, ay * s)
    g.lineTo(rx * s, ry * s)
    g.stroke()
    chip(g, passLine(e), ((ax + rx) / 2) * s, ((ay + ry) / 2) * s - 6, AMBER, true)
  }
  if (ball) {
    g.strokeStyle = AMBER
    g.lineWidth = 2
    g.beginPath()
    g.arc(ball[0] * s, ball[1] * s, 7, 0, Math.PI * 2)
    g.stroke()
  }
}

function chip(
  g: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  col: string,
  filled = false,
) {
  const pad = 3
  const m = g.measureText(text)
  const hh = 14
  if (filled) {
    g.fillStyle = 'rgba(13,16,20,0.85)'
    g.fillRect(x, y - hh, m.width + pad * 2, hh + 1)
  }
  g.fillStyle = col
  g.fillText(text, x + pad, y)
}
