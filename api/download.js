import { Innertube, UniversalCache } from 'youtubei.js'

function videoIdCikar(url) {
  try {
    const u = new URL(url)
    if (u.hostname === 'youtu.be') return u.pathname.slice(1).split('?')[0]
    return u.searchParams.get('v')
  } catch { return null }
}

export default async function handler(req, res) {
  const { url, poToken, visitorData } = req.query

  if (!url) return res.status(400).json({ hata: 'URL eksik.' })

  const videoId = videoIdCikar(url)
  if (!videoId || videoId.length !== 11)
    return res.status(400).json({ hata: 'Geçersiz YouTube URL.' })

  try {
    const ytConfig = { generate_session_locally: true }

    // Client'tan PO token geldiyse kullan
    if (poToken && visitorData) {
      ytConfig.po_token = poToken
      ytConfig.visitor_data = visitorData
    }

    const yt = await Innertube.create(ytConfig)
    const bilgi = await yt.getInfo(videoId)
    const baslik = (bilgi.basic_info.title ?? videoId).replace(/[^\w\s]/gi, '').trim()

    const tumFormatlar = [
      ...(bilgi.streaming_data?.formats ?? []),
      ...(bilgi.streaming_data?.adaptive_formats ?? []),
    ]

    if (tumFormatlar.length === 0) {
      return res.status(404).json({
        hata: 'Format bulunamadı. PO Token gerekiyor olabilir.',
        poTokenGerekli: true,
      })
    }

    const format = tumFormatlar
      .filter((f) => f.has_audio && f.has_video && f.mime_type?.includes('video/mp4'))
      .sort((a, b) => (b.height ?? 0) - (a.height ?? 0))[0]
      ?? tumFormatlar
        .filter((f) => f.has_video && f.mime_type?.includes('video/mp4'))
        .sort((a, b) => (b.height ?? 0) - (a.height ?? 0))[0]

    if (!format) return res.status(404).json({ hata: 'MP4 format yok.' })

    const videoUrl = format.url ?? format.decipher(yt.session.player)
    if (!videoUrl) return res.status(500).json({ hata: 'URL çözümlenemedi.' })

    res.setHeader('Content-Disposition', `attachment; filename="${baslik}.mp4"`)
    return res.redirect(302, videoUrl)

  } catch (err) {
    console.error('[yt-indir]', err.message)
    return res.status(500).json({ hata: err.message })
  }
}
