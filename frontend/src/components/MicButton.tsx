import { useEffect, useRef, useState } from 'react'
import { ApiError, canTranscribe, transcribeQuestion } from '@/net/api'
import { useT } from '@/state/useSession'

/** What the browser can record, best first. Speech takes all three. */
const TYPES = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4']
/** A tap is not a question. */
const MIN_MS = 450
/** A question, not a speech. */
const MAX_MS = 15_000

type Phase = 'idle' | 'starting' | 'listening' | 'working'
type Note = 'micShort' | 'micBlocked' | 'micMissed' | null

const recordable = () =>
  typeof window !== 'undefined' &&
  typeof window.MediaRecorder !== 'undefined' &&
  !!navigator.mediaDevices?.getUserMedia

/**
 * Hold to ask out loud. Press and hold (pointer, or Space/Enter when focused), speak, let go.
 * The clip goes to the gateway, Azure AI Speech turns it into words in the viewer's language,
 * and `onText` gets them. Hidden when the browser cannot record or Speech is not available.
 */
export function MicButton({
  matchId,
  lang,
  onText,
  disabled = false,
}: {
  matchId: string
  lang: string
  onText: (text: string) => void
  disabled?: boolean
}) {
  const t = useT()
  const [available, setAvailable] = useState(false)
  const [phase, setPhase] = useState<Phase>('idle')
  const [note, setNote] = useState<Note>(null)
  const button = useRef<HTMLButtonElement>(null)
  const rec = useRef<{
    recorder: MediaRecorder
    stream: MediaStream
    chunks: Blob[]
    since: number
    audio: AudioContext | null
    raf: number
    timer: number
  } | null>(null)
  // Let go before the recorder was ready (the permission prompt, say): do not start after all.
  const held = useRef(false)

  useEffect(() => {
    let live = true
    if (recordable()) void canTranscribe().then((ok) => live && setAvailable(ok))
    return () => {
      live = false
    }
  }, [])

  useEffect(() => () => teardown(), [])

  function teardown() {
    const r = rec.current
    if (!r) return
    rec.current = null
    window.cancelAnimationFrame(r.raf)
    window.clearTimeout(r.timer)
    r.stream.getTracks().forEach((tr) => tr.stop())
    void r.audio?.close().catch(() => undefined)
    button.current?.style.setProperty('--level', '0')
  }

  async function start() {
    if (phase !== 'idle' || disabled) return
    held.current = true
    setNote(null)
    setPhase('starting')
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setPhase('idle')
      setNote('micBlocked')
      return
    }
    if (!held.current) {
      stream.getTracks().forEach((tr) => tr.stop())
      setPhase('idle')
      setNote('micShort')
      return
    }
    const mimeType = TYPES.find((m) => MediaRecorder.isTypeSupported(m))
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    const chunks: Blob[] = []
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data)
    recorder.start()
    rec.current = {
      recorder,
      stream,
      chunks,
      since: performance.now(),
      audio: null,
      raf: 0,
      timer: window.setTimeout(() => void stop(), MAX_MS),
    }
    meter(stream)
    setPhase('listening')
  }

  /** Drive the ring around the button from the input level, without re-rendering. */
  function meter(stream: MediaStream) {
    const r = rec.current
    if (!r || typeof AudioContext === 'undefined') return
    const audio = new AudioContext()
    const analyser = audio.createAnalyser()
    analyser.fftSize = 256
    audio.createMediaStreamSource(stream).connect(analyser)
    const data = new Uint8Array(analyser.fftSize)
    r.audio = audio
    const tick = () => {
      analyser.getByteTimeDomainData(data)
      let peak = 0
      for (const v of data) peak = Math.max(peak, Math.abs(v - 128))
      button.current?.style.setProperty('--level', Math.min(1, peak / 48).toFixed(2))
      if (rec.current) rec.current.raf = window.requestAnimationFrame(tick)
    }
    r.raf = window.requestAnimationFrame(tick)
  }

  async function stop() {
    held.current = false
    const r = rec.current
    if (!r) return
    const long = performance.now() - r.since >= MIN_MS
    const done = new Promise<void>((res) => (r.recorder.onstop = () => res()))
    r.recorder.stop()
    await done
    teardown()
    if (!long) {
      setPhase('idle')
      setNote('micShort')
      return
    }
    setPhase('working')
    try {
      const blob = new Blob(r.chunks, { type: r.recorder.mimeType || 'audio/webm' })
      const text = await transcribeQuestion(matchId, blob, lang)
      setPhase('idle')
      onText(text)
    } catch (err) {
      setPhase('idle')
      setNote('micMissed')
      if (!(err instanceof ApiError)) console.warn('transcribe failed', err)
    }
  }

  if (!available) return null
  const listening = phase === 'listening'
  const label = phase === 'working' ? t('micWorking') : listening ? t('micListening') : t('micHold')
  return (
    <div className="flex min-w-0 items-center gap-3">
      <button
        ref={button}
        type="button"
        aria-label={t('micHold')}
        aria-pressed={listening}
        aria-describedby="mic-status"
        disabled={disabled || phase === 'working'}
        onPointerDown={(e) => {
          e.preventDefault()
          e.currentTarget.setPointerCapture(e.pointerId)
          void start()
        }}
        onPointerUp={() => void stop()}
        onPointerCancel={() => void stop()}
        onKeyDown={(e) => {
          if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) {
            e.preventDefault()
            void start()
          }
        }}
        onKeyUp={(e) => {
          if (e.key === ' ' || e.key === 'Enter') void stop()
        }}
        onContextMenu={(e) => e.preventDefault()}
        className={`mic relative grid size-11 shrink-0 touch-none select-none place-items-center border transition-colors duration-150 disabled:opacity-40 ${
          listening
            ? 'border-amber bg-amber text-ink'
            : 'border-white/30 text-text hover:border-amber'
        }`}
      >
        <svg viewBox="0 0 16 16" className="size-[18px]" aria-hidden>
          <rect x="5.5" y="1.5" width="5" height="8.5" rx="2.5" fill="currentColor" />
          <path
            d="M3 8a5 5 0 0 0 10 0M8 13v2"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </button>
      <p
        id="mic-status"
        aria-live="polite"
        className={`min-w-0 text-[13px] leading-snug ${note ? 'text-amber' : 'text-muted'}`}
      >
        {phase === 'working' && (
          <span className="pulse-soft me-2 inline-block size-2 rounded-full bg-amber" aria-hidden />
        )}
        {note && phase === 'idle' ? t(note) : label}
      </p>
    </div>
  )
}
