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

/** Like niceTicks, but the first tick is at or below `min` and the last at or above `max`, so
 * every data point falls inside the gridlines. */
export function coveringTicks(min: number, max: number, count = 5): number[] {
  const ticks = niceTicks(min, max, count)
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : 1
  while (ticks[0] > min) ticks.unshift(Number((ticks[0] - step).toFixed(10)))
  while (ticks[ticks.length - 1] < max) ticks.push(Number((ticks[ticks.length - 1] + step).toFixed(10)))
  return ticks
}

// Categorical palette in fixed order (cluster 0 = least volatile), checked for colour-vision
// deficiency with the dataviz palette validator; a white ring separates overlapping dots.
export const CLUSTER_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']

/** Allocation sleeves in fixed order, coloured by the same palette (never by rank). */
export const SLEEVE_COLORS: Record<string, string> = {
  large_cap: CLUSTER_COLORS[0],
  mid_small_cap: CLUSTER_COLORS[1],
  long_debt: CLUSTER_COLORS[2],
  short_debt: CLUSTER_COLORS[3],
  // Rows of the Phase 9 rebalancing table that no recommendation uses.
  other_equity: CLUSTER_COLORS[4],
  other: CLUSTER_COLORS[6],
}
