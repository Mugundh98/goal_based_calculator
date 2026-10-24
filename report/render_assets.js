// Renders the report's diagrams (Mermaid) and formulas (LaTeX, via KaTeX) to PNG files.
//
//   node render_assets.js build/assets/jobs.json
//
// jobs.json: [{ "id": "<hash>", "kind": "mermaid" | "latex", "source": "..." }, ...]
// Writes build/assets/<id>.png for every job whose PNG does not exist yet (a cache: the id is a
// hash of the source). Uses the Chromium that Playwright installed for the end-to-end tests.
const fs = require('fs')
const path = require('path')
const { pathToFileURL } = require('url')
const { chromium } = require('../frontend/node_modules/playwright-core')

const here = __dirname
const katexDir = path.join(here, 'node_modules', 'katex', 'dist')
const mermaidJs = path.join(here, 'node_modules', 'mermaid', 'dist', 'mermaid.min.js')

async function main() {
  const jobsFile = process.argv[2]
  const outDir = path.dirname(jobsFile)
  const jobs = JSON.parse(fs.readFileSync(jobsFile, 'utf8')).filter(
    (job) => !fs.existsSync(path.join(outDir, `${job.id}.png`)),
  )
  if (jobs.length === 0) {
    console.log('assets: all cached')
    return
  }
  const page_html = `<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="${pathToFileURL(path.join(katexDir, 'katex.min.css'))}">
<script src="${pathToFileURL(path.join(katexDir, 'katex.min.js'))}"></script>
<script src="${pathToFileURL(mermaidJs)}"></script>
<style>
  body { margin: 0; background: white; font-family: Arial, sans-serif; }
  #box { display: inline-block; padding: 12px; background: white; }
  #box .katex { font-size: 1.45em; }
</style></head><body><div id="box"></div></body></html>`
  const htmlFile = path.join(outDir, '_render.html')
  fs.writeFileSync(htmlFile, page_html)

  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1000, height: 800 }, deviceScaleFactor: 2.5 })
  await page.goto(pathToFileURL(htmlFile).href)
  await page.evaluate(() =>
    window.mermaid.initialize({
      startOnLoad: false,
      theme: 'neutral',
      fontFamily: 'Arial, sans-serif',
      flowchart: { htmlLabels: false, curve: 'basis' },
      sequence: { useMaxWidth: false },
      er: { useMaxWidth: false },
    }),
  )
  let failed = 0
  for (const job of jobs) {
    try {
      await page.evaluate(async ({ kind, source, id }) => {
        const box = document.getElementById('box')
        box.innerHTML = ''
        if (kind === 'latex') {
          window.katex.render(source, box, { displayMode: true, throwOnError: true })
        } else {
          const { svg } = await window.mermaid.render(`m${id}`, source)
          box.innerHTML = svg
          const el = box.querySelector('svg')
          // Draw at its natural size (no max-width squeeze), up to the viewport width.
          el.style.maxWidth = 'none'
          const vb = el.viewBox.baseVal
          if (vb && vb.width) el.setAttribute('width', vb.width)
        }
      }, job)
      const size = await page.locator('#box').boundingBox()
      if (size && size.width > 990) {
        await page.setViewportSize({ width: Math.ceil(size.width) + 20, height: 800 })
      }
      await page.locator('#box').screenshot({ path: path.join(outDir, `${job.id}.png`) })
      await page.setViewportSize({ width: 1000, height: 800 })
      console.log(`rendered ${job.kind} ${job.id}`)
    } catch (error) {
      failed += 1
      console.error(`FAILED ${job.kind} ${job.id}: ${String(error).slice(0, 300)}`)
    }
  }
  await browser.close()
  fs.unlinkSync(htmlFile)
  if (failed) process.exitCode = 1
}

main()
