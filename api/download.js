// Güvenilir Invidious instance'ları (sırayla dener)
const INVIDIOUS = [
  'https://inv.nadeko.net',
  'https://invidious.privacydev.net',
  'https://yt.cdaut.de',
  'https://invidious.nerdvpn.de',
]

function videoIdCikar(url) {
  try {
    const u = new URL(url)
    if (u.hostname === 'youtu.be') return u.pathname.slice(1).split('?')[0]
    return u.searchParams.get('v')
  } catch { return null }
}

async function formatGetir(videoId) {
  for (const base of INVIDIOUS) {
    try {
      const res = await fetch(
        `${base}/api/v1/videos/${videoId}?fields=title,formatStreams`,
        { signal: AbortSignal.timeout(6000) }
      )
      if (!res.ok) continue
      const data = await res.json()
      if (data.formatStreams?.length) return data
    } catch {
      continue // bir sonraki instance'ı dene
    }
  }
  return null
}

export default async function handler(req, res) {
  const { url } = req.query

  if (!url) return res.status(400).json({ hata: 'URL eksik.' })

  const videoId = videoIdCikar(url)
  if (!videoId || videoId.length !== 11)
    return res.status(400).json({ hata: 'Geçersiz YouTube URL.' })

  const data = await formatGetir(videoId)

  if (!data) {
    return res.status(503).json({ hata: 'Tüm kaynaklar yanıt vermedi, tekrar dene.' })
  }

  const baslik = (data.title ?? videoId).replace(/[^\w\s]/gi, '').trim()

  // formatStreams → ses+video birleşik, mp4 tercih et
  const format =
    data.formatStreams.find((f) => f.container === 'mp4') ??
    data.formatStreams[0]

  if (!format?.url) {
    return res.status(404).json({ hata: 'İndirilebilir format bulunamadı.' })
  }

  res.setHeader('Content-Disposition', `attachment; filename="${baslik}.mp4"`)
  return res.redirect(302, format.url)
}
