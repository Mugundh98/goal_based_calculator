import type { ReactNode } from 'react'

/**
 * A small Markdown renderer for the assistant's answers: headings, paragraphs, bullet and
 * numbered lists, tables, rules, **bold**, *italic* and `code`. It builds React elements and
 * never inserts HTML, so text from the model cannot run script in the page (no XSS).
 */
export function MarkdownText({ text }: { text: string }) {
  return <div className="space-y-2 text-sm leading-relaxed">{blocks(text)}</div>
}

function inline(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*|_[^_\s][^_]*_)/g)
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={key}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2)
      return (
        <code key={key} className="rounded bg-slate-100 px-1 text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      )
    if ((part.startsWith('*') && part.endsWith('*')) || (part.startsWith('_') && part.endsWith('_')))
      if (part.length > 2) return <em key={key}>{part.slice(1, -1)}</em>
    return part
  })
}

const isTableRow = (line: string) => /^\s*\|.*\|\s*$/.test(line)
const isSeparator = (line: string) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line)
const cells = (line: string) =>
  line
    .trim()
    .replace(/^\||\|$/g, '')
    .split('|')
    .map((c) => c.trim())

function blocks(text: string): ReactNode[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const out: ReactNode[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const key = `b${i}`
    if (!line.trim()) {
      i++
    } else if (/^#{1,4}\s/.test(line)) {
      out.push(
        <p key={key} className="pt-1 font-semibold text-slate-900">
          {inline(line.replace(/^#{1,4}\s+/, ''), key)}
        </p>,
      )
      i++
    } else if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      out.push(<hr key={key} className="border-slate-200" />)
      i++
    } else if (isTableRow(line) && i + 1 < lines.length && isSeparator(lines[i + 1])) {
      const head = cells(line)
      const rows: string[][] = []
      i += 2
      while (i < lines.length && isTableRow(lines[i])) rows.push(cells(lines[i++]))
      out.push(
        <div key={key} className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                {head.map((h, j) => (
                  <th key={j} className="py-1 pr-4 font-medium">
                    {inline(h, `${key}h${j}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, r) => (
                <tr key={r} className="border-b border-slate-100">
                  {row.map((c, j) => (
                    <td key={j} className="py-1 pr-4 tabular-nums">
                      {inline(c, `${key}r${r}c${j}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
    } else if (/^\s*([-*•])\s+/.test(line) || /^\s*\d+[.)]\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line)
      const items: string[] = []
      const pattern = ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*•]\s+/
      while (i < lines.length && pattern.test(lines[i])) items.push(lines[i++].replace(pattern, ''))
      const List = ordered ? 'ol' : 'ul'
      out.push(
        <List key={key} className={`space-y-1 pl-5 ${ordered ? 'list-decimal' : 'list-disc'}`}>
          {items.map((item, j) => (
            <li key={j}>{inline(item, `${key}i${j}`)}</li>
          ))}
        </List>,
      )
    } else {
      const paragraph: string[] = []
      while (
        i < lines.length &&
        lines[i].trim() &&
        !/^#{1,4}\s/.test(lines[i]) &&
        !/^\s*([-*•]|\d+[.)])\s+/.test(lines[i]) &&
        !isTableRow(lines[i])
      )
        paragraph.push(lines[i++])
      out.push(<p key={key}>{inline(paragraph.join(' '), key)}</p>)
    }
  }
  return out
}
