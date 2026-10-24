// Builds the project presentation: report/build/GoalWise_Presentation.pptx
//
//   node report/build_slides.js        (after build_report.py and slide_assets.py)
//
// A structured deck: one theme (fonts and colours), three layouts (title, content, dark), and
// slides filled through placeholders, so it restyles in one place and edits cleanly in PowerPoint.
const fs = require('fs')
const path = require('path')
const pptxgen = require('pptxgenjs')

const SKILL_THEME = path.join(
  process.env.LOCALAPPDATA || '',
  'Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/local-agent-mode-sessions/skills-plugin/428e64e6-6d43-484a-a0a0-b3f213c84596/5b09012e-c6ce-4c02-ba62-f25fabd4d80a/skills/pptx/scripts/apply_theme.js',
)
const here = __dirname
const assets = JSON.parse(fs.readFileSync(path.join(here, 'build', 'slide_assets.json'), 'utf8'))
const shot = (name) => path.join(assets.screenshots, name)
const d = assets.details
const blank = (v) => (v && v.trim() ? v : '____________________')

const THEME = {
  name: 'GoalWise',
  headFontFace: 'Cambria',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '1F2933', lt1: 'FFFFFF', dk2: '0B3B32', lt2: 'E7F5EF',
    accent1: '059669', accent2: 'F59E0B', accent3: '0E7490', accent4: '64748B',
    accent5: '10B981', accent6: 'B45309', hlink: '0E7490', folHlink: '6B21A8',
  },
}
const HEX = THEME.colors

const pres = new pptxgen()
pres.layout = 'LAYOUT_16x9' // 10 x 5.625 in
pres.title = 'GoalWise – MCA Project Presentation'
pres.author = d.learner_name || 'GoalWise'
pres.subject = 'Goal-based investment and retirement planning'
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace }
const C = pres.SchemeColor

// --- Layouts -----------------------------------------------------------------------------------
pres.defineSlideMaster({
  title: 'TITLE',
  background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 1.35, w: 8.8, h: 1.2,
      fontFace: THEME.headFontFace, fontSize: 44, bold: true, color: C.background1, valign: 'bottom' },
      text: 'Title' } },
    { placeholder: { options: { name: 'body', type: 'body', x: 0.6, y: 2.6, w: 8.8, h: 1.0,
      fontFace: THEME.bodyFontFace, fontSize: 18, color: C.background2, valign: 'top' }, text: 'Subtitle' } },
  ],
})
pres.defineSlideMaster({
  title: 'CONTENT',
  background: { color: HEX.lt1 },
  margin: [0.4, 0.5, 0.45, 0.5],
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.5, y: 0.28, w: 9.0, h: 0.72,
      fontFace: THEME.headFontFace, fontSize: 30, bold: true, color: C.text2, valign: 'middle' },
      text: 'Title' } },
    { text: { text: 'GoalWise · MCA Project, Andhra University CDOE', options: { x: 0.5, y: 5.22, w: 6, h: 0.3,
      fontFace: THEME.bodyFontFace, fontSize: 10, color: C.accent4 } } },
  ],
  slideNumber: { x: 9.0, y: 5.22, w: 0.5, h: 0.3, fontFace: THEME.bodyFontFace, fontSize: 10, color: C.accent4, align: 'right' },
})
pres.defineSlideMaster({
  title: 'DARK',
  background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.5, y: 0.35, w: 9.0, h: 0.8,
      fontFace: THEME.headFontFace, fontSize: 32, bold: true, color: C.background1, valign: 'middle' },
      text: 'Title' } },
  ],
  slideNumber: { x: 9.0, y: 5.22, w: 0.5, h: 0.3, fontFace: THEME.bodyFontFace, fontSize: 10, color: C.background2, align: 'right' },
})

// --- Helpers -----------------------------------------------------------------------------------
let section = ''
function slide(master, title, notes) {
  const s = pres.addSlide({ masterName: master, sectionTitle: section })
  s.addText(title, { placeholder: 'title' })
  if (notes) s.addNotes(notes)
  return s
}
function newSection(title) {
  section = title
  pres.addSection({ title })
}
const text = (s, value, opts) => s.addText(value, { isTextBox: true, fontFace: THEME.bodyFontFace, color: C.text1, margin: 0, ...opts })
function card(s, x, y, w, h, name, fill = C.background2) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill }, objectName: name })
}
function badge(s, x, y, label, fill = C.accent1) {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color: fill }, line: { color: fill } })
  text(s, String(label), { x, y, w: 0.42, h: 0.42, fontSize: 15, bold: true, color: fill === C.accent2 ? C.text2 : C.background1, align: 'center', valign: 'middle' })
}
function bullets(s, items, opts) {
  s.addText(
    items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1 } })),
    { isTextBox: true, fontFace: THEME.bodyFontFace, fontSize: 15, color: C.text1, paraSpaceAfter: 6, valign: 'top', margin: 0, ...opts },
  )
}
function stat(s, x, y, w, value, label, color = C.accent1, labelH = 0.55) {
  text(s, value, { x, y, w, h: 0.7, fontSize: 34, bold: true, color, fontFace: THEME.headFontFace })
  text(s, label, { x, y: y + 0.7, w, h: labelH, fontSize: 13, color: C.text1, valign: 'top' })
}
function picture(s, file, x, y, w, h, name) {
  s.addImage({ path: file, x, y, w, h, sizing: { type: 'contain', w, h }, objectName: name, altText: name })
}
const chartText = {
  catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt', dataLabelFontFace: '+mn-lt',
  titleFontFace: '+mn-lt', legendFontFace: '+mn-lt',
  catAxisLabelColor: '475569', valAxisLabelColor: '475569', dataLabelColor: '1F2933',
  catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, dataLabelFontSize: 11, titleFontSize: 13,
  titleColor: '1F2933', valGridLine: { color: 'E2E8F0', size: 0.75 }, catGridLine: { style: 'none' },
}

// --- 1. Title ----------------------------------------------------------------------------------
newSection('Introduction')
{
  const s = slide('TITLE', 'GoalWise',
    'Introduce the project: a web application that plans each financial goal, measures its chance of success and tracks real investments.')
  s.addText('An ML-driven goal-based investment and retirement planning system with a conversational AI assistant', { placeholder: 'body' })
  text(s, `MCA Project · Centre for Distance and Online Education, Andhra University`, { x: 0.6, y: 3.75, w: 8.8, h: 0.35, fontSize: 14, color: C.background2 })
  text(s, `Learner: ${blank(d.learner_name)}   ·   Guide: ${blank(d.guide_name)}`, { x: 0.6, y: 4.15, w: 8.8, h: 0.35, fontSize: 14, color: C.background2 })
}

// --- 2. The problem ----------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'One number hides three problems',
    'Existing calculators give a single projected value. They hide inflation, the uncertainty of returns and the drift of real investments from the plan.')
  const items = [
    ['₹44.8 L', 'Inflation', '₹25 L of education today costs ₹44.8 L in 10 years at 6% inflation'],
    ['~50%', 'Uncertainty', 'Investing exactly the “required” SIP reaches the goal only about half the time'],
    ['Drift', 'Tracking', 'Real investments move away from the plan, and nobody notices until it is late'],
  ]
  items.forEach(([big, head, body], i) => {
    const x = 0.5 + i * 3.05
    card(s, x, 1.3, 2.85, 3.55, `problem-${i + 1}`)
    text(s, big, { x: x + 0.25, y: 1.55, w: 2.4, h: 0.8, fontSize: 36, bold: true, color: i === 1 ? C.accent2 : C.accent1, fontFace: THEME.headFontFace })
    text(s, head, { x: x + 0.25, y: 2.45, w: 2.4, h: 0.45, fontSize: 18, bold: true, color: C.text2 })
    text(s, body, { x: x + 0.25, y: 2.95, w: 2.4, h: 1.7, fontSize: 15, valign: 'top' })
  })
}

// --- 3. Objectives -----------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Objectives',
    'Ten objectives, from risk profiling to deployment. Each became one phase of the project.')
  const objectives = [
    'Transparent risk profile', 'Goal plans with inflation and step-up', 'Chance of success by simulation',
    'Two-phase retirement plan', 'Indian market data pipeline', 'Explained ML fund ranking',
    'Allocation and fund advice', 'Track real investments', 'Grounded AI assistant', 'Reports, admin, tests, deployment',
  ]
  objectives.forEach((o, i) => {
    const col = i % 2
    const row = Math.floor(i / 2)
    const x = 0.5 + col * 4.6
    const y = 1.25 + row * 0.76
    badge(s, x, y + 0.05, i + 1, i < 4 ? C.accent1 : i < 8 ? C.accent3 : C.text2)
    text(s, o, { x: x + 0.6, y, w: 3.85, h: 0.52, fontSize: 16, valign: 'middle' })
  })
}

// --- 4. What GoalWise does -----------------------------------------------------------------------
{
  const s = slide('CONTENT', 'What GoalWise does',
    'The user journey: profile and risk, goals, simulation, recommendation, tracking, and the assistant across all of them.')
  const steps = [
    ['Profile', 'Finances and risk tolerance'], ['Plan', 'Goals and retirement in today\'s rupees'],
    ['Simulate', '10,000 market futures per goal'], ['Recommend', 'Asset mix and funds per goal'],
    ['Track', 'Real investments vs the plan'], ['Ask', 'Plain-language assistant'],
  ]
  steps.forEach(([head, body], i) => {
    const x = 0.5 + i * 1.53
    card(s, x, 1.5, 1.38, 2.6, `step-${i + 1}`, i === 2 ? 'FEF3C7' : C.background2)
    badge(s, x + 0.48, 1.7, i + 1, i === 2 ? C.accent2 : C.accent1)
    text(s, head, { x: x + 0.1, y: 2.3, w: 1.18, h: 0.45, fontSize: 17, bold: true, color: C.text2, align: 'center' })
    text(s, body, { x: x + 0.1, y: 2.8, w: 1.18, h: 1.2, fontSize: 13, align: 'center', valign: 'top' })
  })
  text(s, 'Every number comes from one set of backend calculations, shared by the pages, the PDF report and the assistant.', { x: 0.5, y: 4.4, w: 9, h: 0.6, fontSize: 15, italic: true, color: C.text2 })
}

// --- 5. Architecture ---------------------------------------------------------------------------
newSection('Design')
{
  const s = slide('CONTENT', 'Architecture',
    'Three tiers: React single-page app on Vercel, FastAPI on Render in Docker, PostgreSQL with pgvector on Neon. A nightly GitHub Actions job loads market data; the assistant calls the Gemini API.')
  picture(s, assets.architecture, 0.5, 1.15, 5.6, 3.95, 'architecture-diagram')
  bullets(s, [
    'Three tiers: React app, FastAPI REST API, PostgreSQL + pgvector',
    'Routes → services → models; pure finance, simulation and ML modules',
    'Stateless JWT authentication',
    'Nightly data refresh; Gemini for the assistant',
  ], { x: 6.35, y: 1.3, w: 3.15, h: 3.7, fontSize: 14 })
}

// --- 6. Technology -----------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Technology stack',
    'Modern open-source stack chosen for data-intensive web applications; Python for the statistics and machine learning.')
  const cards = [
    ['Frontend', 'React 19, TypeScript, Vite, Tailwind, TanStack Query'],
    ['Backend', 'Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic'],
    ['Database', 'PostgreSQL 16 with pgvector; 25 tables, 14 migrations'],
    ['Data science', 'NumPy, pandas, statsmodels, arch, hmmlearn, LightGBM, SHAP'],
    ['AI', 'Gemini function calling, embeddings, retrieval'],
    ['Quality and hosting', 'pytest, Vitest, Playwright, GitHub Actions; Vercel, Render, Neon'],
  ]
  cards.forEach(([head, body], i) => {
    const x = 0.5 + (i % 3) * 3.05
    const y = 1.25 + Math.floor(i / 3) * 1.95
    card(s, x, y, 2.85, 1.75, `tech-${i + 1}`)
    text(s, head, { x: x + 0.2, y: y + 0.18, w: 2.45, h: 0.4, fontSize: 18, bold: true, color: C.accent1 })
    text(s, body, { x: x + 0.2, y: y + 0.62, w: 2.45, h: 1.0, fontSize: 14, valign: 'top' })
  })
}

// --- 7. Data -----------------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Real Indian market data',
    'All data is free and public: AMFI NAVs, NSE index closes via Yahoo Finance, MOSPI CPI. Loads are idempotent and every run is logged.')
  stat(s, 0.5, 1.35, 2.1, '14,136', 'mutual fund schemes (AMFI)')
  stat(s, 2.75, 1.35, 2.1, '1,482', 'funds with full daily history')
  stat(s, 5.0, 1.35, 2.1, '2.55 M', 'daily NAVs stored', C.accent3)
  stat(s, 7.25, 1.35, 2.25, '164', 'months of equity and debt returns', C.accent3)
  card(s, 0.5, 3.3, 9.0, 1.6, 'data-sources')
  bullets(s, [
    'Sources: AMFI NAVAll.txt and history, NSE indices (Nifty 500), MOSPI consumer price index',
    'Cleaning: parsed and validated rows, idempotent upserts, unit-change correction, every rejection logged',
  ], { x: 0.75, y: 3.5, w: 8.5, h: 1.3, fontSize: 15 })
}

// --- 8. Goal mathematics -------------------------------------------------------------------------
newSection('Methods')
{
  const s = slide('CONTENT', 'Goal mathematics',
    'Target inflated to its year; SIP as an annuity due with an effective monthly rate; the required SIP solves for P after subtracting grown savings.')
  card(s, 0.5, 1.25, 5.3, 3.65, 'formulas')
  picture(s, assets.formulas[0], 0.7, 1.45, 4.9, 1.0, 'goal-formulas')
  text(s, 'i = (1 + r)^(1/12) − 1  (effective monthly rate)', { x: 0.7, y: 2.6, w: 4.9, h: 0.4, fontSize: 14, color: C.text2 })
  text(s, 'Verified against hand calculations to the paisa and against a month-by-month simulation.', { x: 0.7, y: 3.15, w: 4.9, h: 0.9, fontSize: 14, valign: 'top' })
  text(s, 'Worked example', { x: 6.1, y: 1.3, w: 3.4, h: 0.4, fontSize: 18, bold: true, color: C.accent1 })
  bullets(s, [
    'Education costing ₹25 L today, in 10 years',
    'At 6% inflation: target ₹44.8 L',
    'SIP needed at 10% a year: about ₹22,200',
    'Savings and yearly step-ups lower it',
  ], { x: 6.1, y: 1.8, w: 3.4, h: 3.0, fontSize: 15 })
}

// --- 9. Monte Carlo ------------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Monte Carlo simulation',
    'Each goal is simulated along 10,000 market paths. Four return models capture fat tails, clustered volatility and regimes. The output is a probability, a range and the SIP for a chosen certainty.')
  picture(s, shot('phase-05-simulation.jpg'), 0.5, 1.15, 5.4, 3.95, 'simulation-screenshot')
  bullets(s, [
    'Normal: the textbook baseline',
    'Block bootstrap: 12-month blocks of real history',
    'GARCH(1,1): volatility clusters',
    'Hidden Markov model: bull and bear regimes',
    'SIP for a 50%, 75% or 90% chance',
  ], { x: 6.15, y: 1.3, w: 3.35, h: 3.7, fontSize: 14 })
}

// --- 10. Key finding ---------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Certainty has a price',
    'Investing the plan\'s required SIP reaches the goal in about half of the simulated futures under every model. A 90% chance costs 7–9% more SIP for a 3-year goal and 91–99% more for a 25-year goal.')
  s.addChart(pres.charts.BAR, [
    { name: 'Plan SIP (₹)', labels: ['Car, 3 y', 'House, 7 y', 'Education, 10 y', 'Education, 15 y', 'Wealth, 25 y'], values: [23179, 24546, 21529, 12482, 24817] },
    { name: 'SIP for a 90% chance (₹)', labels: ['Car, 3 y', 'House, 7 y', 'Education, 10 y', 'Education, 15 y', 'Wealth, 25 y'], values: [24886, 29992, 27694, 19633, 47338] },
  ], {
    x: 0.5, y: 1.15, w: 6.0, h: 3.95, barDir: 'col', barGrouping: 'clustered', chartColors: [HEX.accent4, HEX.accent1],
    showTitle: true, title: 'Monthly SIP: plan vs 90% chance (block bootstrap)', showLegend: true, legendPos: 'b', legendFontSize: 11,
    showValue: false, valAxisLabelFormatCode: '#,##0', ...chartText,
  })
  stat(s, 6.8, 1.35, 2.7, '~50%', 'chance with the plan\'s “required” SIP, under all four models', C.accent2)
  stat(s, 6.8, 3.05, 2.7, '+91%', 'more SIP for a 90% chance on a 25-year goal', C.accent1)
}

// --- 11. Machine learning ----------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Machine learning, evaluated honestly',
    'LightGBM ranks funds within SEBI peer groups using 26 past-only features, validated walk-forward 2021–2025 with SHAP explanations. It matches the momentum baseline rather than beating it; the difference is not significant.')
  s.addChart(pres.charts.BAR, [
    { name: 'Rank correlation', labels: ['LightGBM ranker', 'Last year\'s top funds', 'Random'], values: [0.248, 0.254, -0.006] },
  ], {
    x: 0.5, y: 1.15, w: 5.2, h: 3.95, barDir: 'col', chartColors: [HEX.accent1, HEX.accent3, HEX.accent4],
    showTitle: true, title: 'Rank correlation with next year\'s outcome (2021–2025)', showLegend: false,
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.000', valAxisMinVal: -0.05, valAxisMaxVal: 0.3, ...chartText,
  })
  bullets(s, [
    'Walk-forward validation on 42,435 fund-months',
    'Paired t = −0.26: no significant difference from momentum',
    'Value: explanations (SHAP) and peer comparison',
    'Also: K-Means behaviour clusters, SARIMA inflation forecast',
  ], { x: 6.0, y: 1.3, w: 3.5, h: 3.7, fontSize: 14 })
}

// --- 12. Recommendations -----------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Recommendations per goal',
    'A glide path sets equity bounds from the goal horizon and the risk profile; constrained mean-variance optimisation chooses weights for four sleeves; top-ranked funds fill each sleeve.')
  picture(s, shot('phase-08-allocation.jpg'), 0.5, 1.15, 5.4, 3.95, 'allocation-screenshot')
  bullets(s, [
    'Four sleeves: large cap, mid and small cap, long debt, short debt',
    'Glide path: less equity as the goal nears',
    'Mean-variance optimisation (SLSQP) within the bounds',
    'Reasons and an efficient frontier for every goal',
  ], { x: 6.15, y: 1.3, w: 3.35, h: 3.7, fontSize: 14 })
}

// --- 13. Portfolio -----------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Portfolio tracker',
    'Transactions are the source of truth; holdings are rebuilt with FIFO cost in the same database transaction. XIRR uses Newton–Raphson with a bisection fallback. Alerts flag drift and off-track goals.')
  picture(s, shot('phase-09-portfolio.jpg'), 0.5, 1.15, 5.4, 3.95, 'portfolio-screenshot')
  bullets(s, [
    'XIRR on irregular cash flows',
    'FIFO lots, stamp duty, unit changes',
    'Each goal vs its plan; rebalancing alerts',
    'Own NAV, funds added by hand, editable entries',
  ], { x: 6.15, y: 1.3, w: 3.35, h: 3.7, fontSize: 14 })
}

// --- 14. Assistant -----------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'A grounded AI assistant',
    'The model never computes: 10 typed tools run the system\'s own calculations, and explanations are retrieved from 20 knowledge articles in pgvector. Evaluated on 102 questions.')
  stat(s, 0.5, 1.3, 2.2, '97.1%', 'correct tool chosen (102 questions)')
  stat(s, 2.85, 1.3, 2.2, '50 / 50', 'reference numbers reported correctly')
  stat(s, 0.5, 2.95, 2.2, '11 / 11', 'out-of-scope requests refused', C.accent3)
  stat(s, 2.85, 2.95, 2.2, '0 vs 11', 'of 20 explanations had untraceable numbers: with vs without retrieval', C.accent2, 0.85)
  picture(s, shot('phase-10-answer.jpg'), 5.4, 1.15, 4.1, 3.95, 'assistant-screenshot')
}

// --- 15. Testing -------------------------------------------------------------------------------
newSection('Results')
{
  const s = slide('CONTENT', 'Testing',
    'A test pyramid runs on every push in GitHub Actions: 606 backend tests with 92% coverage against a real PostgreSQL, 71 component tests and 7 browser flows. A change merges only when all three jobs pass.')
  const tiers = [
    ['7', 'end-to-end browser flows (Playwright)', 3.0, C.accent2],
    ['71', 'frontend component tests (Vitest)', 4.6, C.accent3],
    ['606', 'backend unit and integration tests (pytest)', 6.2, C.accent1],
  ]
  tiers.forEach(([n, label, w, color], i) => {
    const y = 1.3 + i * 1.2
    const x = 0.5 + (6.2 - w) / 2
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 1.0, rectRadius: 0.08, fill: { color }, line: { color }, objectName: `tier-${i + 1}` })
    text(s, `${n}  ${label}`, { x: x + 0.15, y, w: w - 0.3, h: 1.0, fontSize: 14, bold: true, color: C.background1, align: 'center', valign: 'middle' })
  })
  stat(s, 7.0, 1.35, 2.5, '92%', 'backend code coverage (minimum 90%)')
  stat(s, 7.0, 3.0, 2.5, '3 jobs', 'on every push: backend, frontend, end-to-end', C.accent3)
}

// --- 16. Deployment ----------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Deployed at no cost',
    'Vercel serves the site, Render runs the API in Docker within 512 MB, Neon hosts PostgreSQL. Simulations queue one at a time to fit memory; the waking-up screen explains cold starts.')
  const hosts = [['Vercel', 'React website'], ['Render', 'FastAPI in Docker, 512 MB'], ['Neon', 'PostgreSQL + pgvector']]
  hosts.forEach(([h, b], i) => {
    const y = 1.25 + i * 1.25
    card(s, 0.5, y, 4.3, 1.05, `host-${i + 1}`)
    text(s, h, { x: 0.75, y: y + 0.12, w: 3.8, h: 0.4, fontSize: 18, bold: true, color: C.accent1 })
    text(s, b, { x: 0.75, y: y + 0.55, w: 3.8, h: 0.4, fontSize: 14 })
  })
  picture(s, shot('phase-13-waking.png'), 5.1, 1.25, 4.4, 2.5, 'waking-screen')
  text(s, 'Peak memory 445 MB under three concurrent worst-case simulations', { x: 5.1, y: 3.95, w: 4.4, h: 0.8, fontSize: 14, italic: true, color: C.text2, valign: 'top' })
}

// --- 17. Demo ----------------------------------------------------------------------------------
{
  const s = slide('CONTENT', 'Live demonstration',
    'Walk through the demo household: dashboard, a goal simulation with what-if changes, a recommendation, the portfolio with alerts, an assistant question and the PDF plan.')
  const steps = ['Dashboard and alerts', 'Simulate a goal; change the SIP', 'Recommendation and frontier', 'Portfolio and goal progress', 'Ask the assistant', 'Download the PDF plan']
  steps.forEach((t, i) => {
    const y = 1.25 + i * 0.6
    badge(s, 0.5, y, i + 1, C.accent1)
    text(s, t, { x: 1.1, y, w: 4.2, h: 0.42, fontSize: 16, valign: 'middle' })
  })
  card(s, 5.6, 1.25, 3.9, 2.0, 'demo-link', 'FEF3C7')
  text(s, 'goal-based-calculator-seven.vercel.app', { x: 5.8, y: 1.45, w: 3.5, h: 0.5, fontSize: 15, bold: true, color: C.text2 })
  text(s, 'Demo account: demo@example.com. Open the site a minute early: the free server wakes up on the first visit.', { x: 5.8, y: 2.0, w: 3.5, h: 1.1, fontSize: 13, valign: 'top' })
}

// --- 18. Limitations and future work -------------------------------------------------------------
{
  const s = slide('CONTENT', 'Limitations and future research',
    'Honest limitations, and the research directions they suggest.')
  text(s, 'Limitations', { x: 0.5, y: 1.2, w: 4.3, h: 0.45, fontSize: 18, bold: true, color: C.accent6 })
  bullets(s, [
    'About 14 years of market history',
    'Ranker only matches the momentum baseline',
    'Mutual funds only; no tax computation',
    'Goals simulated independently',
    'Free-tier hosting and model quotas',
  ], { x: 0.5, y: 1.75, w: 4.3, h: 3.2, fontSize: 15 })
  text(s, 'Future research', { x: 5.2, y: 1.2, w: 4.3, h: 0.45, fontSize: 18, bold: true, color: C.accent1 })
  bullets(s, [
    'Household-level simulation of all goals',
    'More asset classes and after-tax planning',
    'Richer fund data; learning-to-rank',
    'Statement import; Indian languages',
    'Studies of saving behaviour',
  ], { x: 5.2, y: 1.75, w: 4.3, h: 3.2, fontSize: 15 })
}

// --- 19. Conclusion ----------------------------------------------------------------------------
newSection('Close')
{
  const s = slide('DARK', 'Conclusion',
    'Close with the three takeaways and invite questions.')
  const points = [
    ['Probabilities, not one number', 'Each goal gets a chance of success and the price of more certainty'],
    ['Models evaluated honestly', 'Every model is compared with simple baselines, and the results are reported as found'],
    ['A tested, deployed system', '684 automated tests on every change; live at no cost'],
  ]
  points.forEach(([head, body], i) => {
    const y = 1.4 + i * 1.2
    badge(s, 0.6, y + 0.05, i + 1, C.accent2)
    text(s, head, { x: 1.25, y, w: 8.2, h: 0.45, fontSize: 20, bold: true, color: C.background1 })
    text(s, body, { x: 1.25, y: y + 0.48, w: 8.2, h: 0.5, fontSize: 15, color: C.background2 })
  })
}

// --- 20. Thank you -----------------------------------------------------------------------------
{
  const s = slide('TITLE', 'Thank you', 'Invite questions; keep the live site open for follow-up demonstrations.')
  s.addText('Questions?', { placeholder: 'body' })
}

async function main() {
  const out = path.join(here, 'build', 'GoalWise_Presentation.pptx')
  await pres.writeFile({ fileName: out })
  if (fs.existsSync(SKILL_THEME)) {
    // The helper lives outside this folder: let it find jszip in report/node_modules.
    process.env.NODE_PATH = path.join(here, 'node_modules')
    require('module').Module._initPaths()
    const { applyTheme } = require(SKILL_THEME)
    await applyTheme(out, THEME)
  } else {
    console.warn('apply_theme.js not found: theme colours left at the Office defaults')
  }
  console.log(`wrote ${out}`)
}

main()
