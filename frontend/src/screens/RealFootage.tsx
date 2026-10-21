import { useEffect, useRef, useState } from 'react'
import { AppNav } from '@/components/AppNav'
import {
  activeBursts,
  activePasses,
  boxesAt,
  foot,
  matchClock,
  passLine,
  trackOf,
  type Box,
  type RealEvent,
  type RealOverlay,
} from '@/core/real'
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
      <AppNav />
      <h1 className="font-display text-[40px] font-bold leading-none sm:text-[52px]">
        The same idea, on real video
      </h1>

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
  const frame = useRef<HTMLDivElement>(null)
  const full = useFullscreen(frame)
  const now = useVideoTime(video)
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
    // The list runs below the fold: bring the video back so the pass is actually seen.
    frame.current?.scrollIntoView({
      block: 'nearest',
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    })
  }
  const toggle = (k: keyof Layers) => setLayers((l) => ({ ...l, [k]: !l[k] }))
  const onScreen = new Set(activePasses(passes, now))

  return (
    <>
      <p className="max-w-[70ch] text-[15px] leading-relaxed text-muted">
        A real university match, filmed from one fixed camera. A model found every player, the ball,
        each pass and each sprint from the pixels. Nothing here is hand-tagged.
      </p>

      <section aria-label="Match video" className="flex flex-col gap-3">
        <div className="overflow-x-auto">
          {/* Full screen goes on this frame, not the video, so the tracking canvas comes too. */}
          <div
            ref={frame}
            className="real-frame min-w-[900px]"
            onDoubleClick={(e) => {
              e.preventDefault()
              full.toggle()
            }}
          >
            <div
              className="real-box relative w-full"
              style={{
                aspectRatio: `${overlay.clip[0]} / ${overlay.clip[1]}`,
                ['--ratio' as string]: overlay.clip[0] / overlay.clip[1],
              }}
            >
              {clip.video ? (
                <video
                  ref={video}
                  src={videoUrl(clip.clip)}
                  disablePictureInPicture
                  muted
                  playsInline
                  preload="auto"
                  className="block size-full bg-black"
                  onClick={() => togglePlay(video.current)}
                />
              ) : (
                <div className="grid size-full place-items-center bg-black/60 p-6 text-center text-[15px]">
                  The video is not on this server, so only the findings are shown below.
                </div>
              )}
              <canvas
                ref={canvas}
                aria-hidden
                className="pointer-events-none absolute inset-0 size-full"
              />
              <button
                className="absolute end-3 top-3 flex h-9 items-center gap-2 border border-white/40 bg-ink/75 px-3 text-[14px] font-medium text-text hover:border-white/80"
                onClick={full.toggle}
                aria-pressed={full.on}
              >
                <svg
                  viewBox="0 0 14 14"
                  className="size-3.5"
                  aria-hidden
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                >
                  {full.on ? (
                    <path d="M5 1v4H1M9 1v4h4M5 13V9H1M9 13V9h4" />
                  ) : (
                    <path d="M1 5V1h4M13 5V1H9M1 9v4h4M13 9v4H9" />
                  )}
                </svg>
                {full.on ? 'Exit full screen' : 'Full screen'}
              </button>
            </div>
            {clip.video && <VideoBar video={video} startS={overlay.start_s} passes={passes} />}
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
                    ? 'border-amber bg-amber/15 text-amber'
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
          <p className="text-[13px] text-muted">
            Times are the match clock, the same as under the video. Pick one to watch it.
          </p>
          <ol className="flex flex-col divide-y divide-white/10 border-y border-white/10">
            {passes.map((e) => (
              <li key={e.t_match + (e.player_id ?? '')}>
                <button
                  aria-current={onScreen.has(e) ? 'true' : undefined}
                  className="grid w-full grid-cols-[4.5rem_1fr] gap-x-3 px-1 py-3 text-start transition-colors hover:bg-white/[0.03] aria-[current]:bg-amber/10"
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

function togglePlay(v: HTMLVideoElement | null) {
  if (!v) return
  if (v.paused) void v.play().catch(() => undefined)
  else v.pause()
}

/** The video's current time, a few times a second (from the element's own timeupdate). */
function useVideoTime(ref: React.RefObject<HTMLVideoElement | null>): number {
  const [t, setT] = useState(0)
  useEffect(() => {
    const v = ref.current
    if (!v) return
    const on = () => setT(v.currentTime)
    // `seeking` too: currentTime already holds the target, so the clock jumps before the
    // frames for it have arrived.
    const events = ['timeupdate', 'seeking', 'seeked'] as const
    events.forEach((e) => v.addEventListener(e, on))
    return () => events.forEach((e) => v.removeEventListener(e, on))
  }, [ref])
  return t
}

/**
 * Play, the match clock and a scrubber with a tick for every pass it found. Replaces the
 * browser's own controls, which counted from 0:00 while the rest of the page uses the match
 * clock.
 */
function VideoBar({
  video,
  startS,
  passes,
}: {
  video: React.RefObject<HTMLVideoElement | null>
  startS: number
  passes: RealEvent[]
}) {
  const t = useVideoTime(video)
  const [duration, setDuration] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    const v = video.current
    if (!v) return
    const meta = () => setDuration(Number.isFinite(v.duration) ? v.duration : 0)
    const sync = () => setPlaying(!v.paused)
    const wait = () => setLoading(true)
    const ready = () => setLoading(false)
    meta()
    sync()
    const on: [string, () => void][] = [
      ['loadedmetadata', meta],
      ['play', sync],
      ['pause', sync],
      ['waiting', wait],
      ['seeking', wait],
      ['playing', ready],
      ['seeked', ready],
      ['canplay', ready],
    ]
    on.forEach(([e, f]) => v.addEventListener(e, f))
    return () => on.forEach(([e, f]) => v.removeEventListener(e, f))
  }, [video])
  const seekTo = (s: number) => {
    const v = video.current
    if (v) v.currentTime = Math.min(Math.max(0, s), duration || s)
  }
  const at = (s: number) => `${duration ? (s / duration) * 100 : 0}%`
  return (
    <div className="real-bar flex h-16 items-center gap-4 bg-ink/90 px-3">
      <button
        className="grid size-10 shrink-0 place-items-center border border-white/30 text-text hover:border-amber"
        onClick={() => togglePlay(video.current)}
        aria-label={playing ? 'Pause' : 'Play'}
      >
        <svg viewBox="0 0 12 12" className="size-3.5" aria-hidden fill="currentColor">
          {playing ? <path d="M2.5 1.5h2.5v9H2.5zM7 1.5h2.5v9H7z" /> : <path d="M3 1.5v9l7-4.5z" />}
        </svg>
      </button>
      <span
        className={`num w-[4.5rem] shrink-0 text-[22px] leading-none text-amber ${loading ? 'pulse-soft' : ''}`}
        dir="ltr"
        aria-busy={loading}
      >
        {matchClock(startS, t)}
      </span>
      <div className="relative h-9 min-w-0 flex-1">
        <div className="absolute inset-x-0 top-1/2 h-[3px] -translate-y-1/2 bg-white/15" />
        <div
          className="absolute start-0 top-1/2 h-[3px] -translate-y-1/2 bg-amber"
          style={{ width: at(t) }}
        />
        {passes.map((e) => (
          <span
            key={e.t_match + (e.player_id ?? '')}
            aria-hidden
            className="absolute top-1/2 h-3 w-[2px] -translate-y-1/2 bg-white/50"
            style={{ left: at(e.t_match) }}
          />
        ))}
        <input
          type="range"
          className="scrub absolute inset-0 size-full"
          min={0}
          max={duration || 1}
          step={0.04}
          value={Math.min(t, duration || t)}
          aria-label="Match time"
          aria-valuetext={matchClock(startS, t)}
          onChange={(e) => seekTo(Number(e.target.value))}
        />
      </div>
      <span className="num hidden shrink-0 text-[14px] text-muted sm:inline" dir="ltr">
        {matchClock(startS, 0)} to {matchClock(startS, duration)}
      </span>
    </div>
  )
}

/** Full screen for one element, tracking the browser's own state (Escape also leaves it). */
function useFullscreen(ref: React.RefObject<HTMLElement | null>) {
  const [on, setOn] = useState(false)
  useEffect(() => {
    const sync = () => {
      const el = document.fullscreenElement
      // A browser that ignores controlsList can still put the bare video in full screen, which
      // would leave the tracking canvas behind. Hand full screen to the frame instead.
      if (el instanceof HTMLVideoElement && ref.current?.contains(el)) {
        void document
          .exitFullscreen()
          .then(() => ref.current?.requestFullscreen())
          .catch(() => undefined)
        return
      }
      setOn(el === ref.current && ref.current !== null)
    }
    document.addEventListener('fullscreenchange', sync)
    return () => document.removeEventListener('fullscreenchange', sync)
  }, [ref])
  const toggle = () => {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined)
    else void ref.current?.requestFullscreen().catch(() => undefined)
  }
  return { on, toggle }
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
