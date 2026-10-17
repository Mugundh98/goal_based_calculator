import { afterEach, describe, expect, it, vi } from 'vitest'

import { ChatRequestError, type StreamEvent, streamMessage } from './chat'

/** A fetch Response whose body arrives in the given pieces, as a real stream does. */
function streamed(pieces: string[], status = 200): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const piece of pieces) controller.enqueue(encoder.encode(piece))
      controller.close()
    },
  })
  return new Response(body, { status, headers: { 'Content-Type': 'text/event-stream' } })
}

afterEach(() => vi.unstubAllGlobals())

describe('streamMessage (server-sent events)', () => {
  it('parses events even when they are split across network chunks', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      streamed([
        'event: tool\ndata: {"name": "list_goals", "status": "running"}\n\n',
        'event: text\ndata: {"text": "You have "}\n\nevent: te',
        'xt\ndata: {"text": "one goal."}\n',
        '\nevent: done\ndata: {"message": {"id": 7, "content": "You have one goal."}}\n\n',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)
    const events: StreamEvent[] = []
    await streamMessage(3, 'my goals?', (e) => events.push(e))

    expect(events.map((e) => e.type)).toEqual(['tool', 'text', 'text', 'done'])
    expect(events.filter((e) => e.type === 'text').map((e) => (e as { text: string }).text).join('')).toBe('You have one goal.')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/chat/sessions/3/messages')
    expect(JSON.parse(init.body)).toEqual({ text: 'my goals?' })
  })

  it("raises the API's reason when the question is refused", async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'You can ask 30 questions an hour.' }), { status: 429 })),
    )
    await expect(streamMessage(3, 'hi', () => {})).rejects.toEqual(new ChatRequestError('You can ask 30 questions an hour.'))
  })
})
