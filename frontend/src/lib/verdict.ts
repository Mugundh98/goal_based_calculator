/** Verdict for a chance of success, with an icon and a word so colour is never the only cue. */
export function verdict(chance: number) {
  if (chance >= 80) return { text: 'Likely', icon: '✓', tone: 'bg-emerald-100 text-emerald-800', bar: 'bg-emerald-600' }
  if (chance >= 50) return { text: 'Uncertain', icon: '!', tone: 'bg-amber-100 text-amber-800', bar: 'bg-amber-500' }
  return { text: 'Unlikely', icon: '✕', tone: 'bg-rose-100 text-rose-800', bar: 'bg-rose-600' }
}
