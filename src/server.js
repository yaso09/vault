import { Hono } from 'hono'
import { serve } from '@hono/node-server'
import { serveStatic } from '@hono/node-server/serve-static'
import { exec } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)
const app = new Hono()

function videoIdCikar(url) {
  try {
    const u = new URL(url)
    if (u.hostname === 'youtu.be') return u.pathname.slice(1).split('?')[0]
    return u.searchParams.get('v')
  } catch { return null }
}

// Statik dosyalar
app.use('/*', serveStatic({ root: './public' }))

// Video bilgisi
app.get('/api/info', async (c) => {
  const url = c.req.query('url')
  if (!url || !videoIdCikar(url))
    return c.json({ hata: 'Geçersiz URL.' }, 400)

  try {
    const { stdout } = await execAsync(
      `yt-dlp --dump-json --no-playlist "${url}"`,
      { timeout: 20000 }
    )
    const d = JSON.parse(stdout)
    return c.json({
      baslik: d.title,
      thumbnail: d.thumbnail,
      sure: d.duration,
      formatlar: (d.formats ?? [])
        .filter(f => f.vcodec !== 'none' && f.acodec !== 'none' && f.ext === 'mp4')
        .map(f => ({ id: f.format_id, kalite: `${f.height}p`, boyut: f.filesize_approx }))
        .filter(f => f.kalite)
        .sort((a, b) => parseInt(b.kalite) - parseInt(a.kalite))
    })
  } catch (err) {
    return c.json({ hata: err.message }, 500)
  }
})

// İndirme
app.get('/api/download', async (c) => {
  const url = c.req.query('url')
  const kalite = c.req.query('kalite') ?? '720'

  if (!url || !videoIdCikar(url))
    return c.json({ hata: 'Geçersiz URL.' }, 400)

  try {
    const format = `bestvideo[ext=mp4][height<=${kalite}]+bestaudio[ext=m4a]/best[ext=mp4][height<=${kalite}]/best[ext=mp4]`

    const { stdout } = await execAsync(
      `yt-dlp -f "${format}" --get-url --no-playlist "${url}"`,
      { timeout: 20000 }
    )

    const satirlar = stdout.trim().split('\n').filter(Boolean)
    const videoUrl = satirlar[0]

    if (!videoUrl) return c.json({ hata: 'URL alınamadı.' }, 404)

    return c.redirect(videoUrl, 302)
  } catch (err) {
    return c.json({ hata: err.message }, 500)
  }
})

const port = process.env.PORT ?? 3000
serve({ fetch: app.fetch, port }, () =>
  console.log(`Sunucu: http://localhost:${port}`)
)
