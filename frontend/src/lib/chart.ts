/** Round tick values: steps of 1, 2 or 5 x a power of ten, about `count` of them. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  const span = max - min || Math.abs(max) || 1
  const rough = span / count
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) ?? 10 * magnitude
  const ticks = []
  for (let t = Math.ceil(min / step) * step; t <= max + step * 1e-9; t += step) ticks.push(Number(t.toFixed(10)))
  return ticks
}
