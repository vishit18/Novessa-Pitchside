import type { Lang } from '@/state/profile'

/**
 * Interface strings for the broadcast chrome. Match prose (insights, commentary) arrives from
 * the agents already in the viewer's language; this file only covers the labels around it.
 */
const en = {
  firstHalf: '1st half',
  secondHalf: '2nd half',
  live: 'Live',
  connecting: 'Connecting',
  reconnecting: 'Reconnecting',
  offline: 'Offline',
  sampleMatch: 'sample match',
  streamDelay: 'Stream delay',
  behindLive: '{s}s behind live',
  replaySpeed: 'Replay speed',
  play: 'Play',
  pause: 'Pause',
  passDifficulty: 'Pass difficulty',
  passDone: '{m} m, completed',
  passLost: '{m} m, lost',
  shotBy: '{name}’s shot',
  earlier: 'From earlier in the match',
  waiting: 'Waiting for kick-off',
  feedDown: 'Feed unavailable',
  feedDownBody: 'The match feed did not start.',
  retry: 'Try again',
  matchLine: '{competition}, matchday {n}, at {venue}',
  momentum: 'Momentum {v} to {team}',
  outcome_saved: 'saved',
  outcome_blocked: 'blocked',
  outcome_off_target: 'off target',
  outcome_goal: 'goal',
}

export type StringKey = keyof typeof en

const es: Record<StringKey, string> = {
  firstHalf: '1.ª parte',
  secondHalf: '2.ª parte',
  live: 'En directo',
  connecting: 'Conectando',
  reconnecting: 'Reconectando',
  offline: 'Sin conexión',
  sampleMatch: 'partido de muestra',
  streamDelay: 'Retraso',
  behindLive: '{s} s por detrás del directo',
  replaySpeed: 'Velocidad',
  play: 'Reanudar',
  pause: 'Pausa',
  passDifficulty: 'Dificultad del pase',
  passDone: '{m} m, completado',
  passLost: '{m} m, perdido',
  shotBy: 'Disparo de {name}',
  earlier: 'Jugada anterior',
  waiting: 'Esperando el saque inicial',
  feedDown: 'Señal no disponible',
  feedDownBody: 'La señal del partido no ha arrancado.',
  retry: 'Reintentar',
  matchLine: '{competition}, jornada {n}, en {venue}',
  momentum: 'Dominio {v} para {team}',
  outcome_saved: 'parada',
  outcome_blocked: 'bloqueado',
  outcome_off_target: 'fuera',
  outcome_goal: 'gol',
}

const ar: Record<StringKey, string> = {
  firstHalf: 'الشوط الأول',
  secondHalf: 'الشوط الثاني',
  live: 'مباشر',
  connecting: 'جارٍ الاتصال',
  reconnecting: 'جارٍ إعادة الاتصال',
  offline: 'غير متصل',
  sampleMatch: 'مباراة تجريبية',
  streamDelay: 'تأخير البث',
  behindLive: 'متأخر {s} ث عن البث المباشر',
  replaySpeed: 'سرعة الإعادة',
  play: 'تشغيل',
  pause: 'إيقاف مؤقت',
  passDifficulty: 'صعوبة التمريرة',
  passDone: '{m} م، ناجحة',
  passLost: '{m} م، مقطوعة',
  shotBy: 'تسديدة {name}',
  earlier: 'من وقت سابق في المباراة',
  waiting: 'بانتظار صافرة البداية',
  feedDown: 'البث غير متاح',
  feedDownBody: 'لم يبدأ بث المباراة.',
  retry: 'أعد المحاولة',
  matchLine: '{competition}، الجولة {n}، على ملعب {venue}',
  momentum: 'الأفضلية {v} لصالح {team}',
  outcome_saved: 'تصدى لها الحارس',
  outcome_blocked: 'صُدّت',
  outcome_off_target: 'خارج المرمى',
  outcome_goal: 'هدف',
}

export const STRINGS: Record<Lang, Record<StringKey, string>> = { en, es, ar }

/** Look up a string and fill {placeholders}. Falls back to English, then to the key. */
export function translate(
  lang: Lang,
  key: StringKey,
  vars: Record<string, string | number> = {},
): string {
  const raw = STRINGS[lang][key] ?? STRINGS.en[key] ?? key
  return raw.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`))
}

/** Translate a shot outcome code like "off_target", passing unknown codes through. */
export function outcomeLabel(lang: Lang, outcome: string): string {
  const key = `outcome_${outcome}` as StringKey
  return key in STRINGS.en ? translate(lang, key) : outcome.replaceAll('_', ' ')
}
