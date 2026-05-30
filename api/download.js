import { Innertube } from 'youtubei.js'

// URL'den video ID çıkar (tüm YouTube formatlarını destekler)
function videoIdCikar(url) {
  try {
    const u = new URL(url)
    if (u.hostname === 'youtu.be') return u.pathname.slice(1).split('?')[0]
    return u.searchParams.get('v')
  } catch {
    return null
  }
}

export default async function handler(req, res) {
  const { url } = req.query

  if (!url) {
    return res.status(400).json({ hata: 'URL parametresi eksik.' })
  }

  const videoId = videoIdCikar(url)
  if (!videoId || videoId.length !== 11) {
    return res.status(400).json({ hata: 'Geçerli bir YouTube URL\'i giriniz.' })
  }

  try {
    const yt = await Innertube.create()

    // getBasicInfo yerine getInfo → tam streaming_data döner
    const bilgi = await yt.getInfo(videoId)
    const baslik = (bilgi.basic_info.title ?? videoId).replace(/[^\w\s]/gi, '').trim()

    const tumFormatlar = [
      ...(bilgi.streaming_data?.formats ?? []),
      ...(bilgi.streaming_data?.adaptive_formats ?? []),
    ]

    if (tumFormatlar.length === 0) {
      return res.status(404).json({ hata: 'Hiç format bulunamadı.', videoId })
    }

    // Önce ses+video birleşik MP4, yoksa en iyi video adaptive MP4
    const birlesik = tumFormatlar
      .filter((f) => f.has_audio && f.has_video && f.mime_type?.includes('video/mp4'))
      .sort((a, b) => (b.height ?? 0) - (a.height ?? 0))

    const format = birlesik[0] ?? tumFormatlar
      .filter((f) => f.has_video && f.mime_type?.includes('video/mp4'))
      .sort((a, b) => (b.height ?? 0) - (a.height ?? 0))[0]

    if (!format) {
      return res.status(404).json({ hata: 'MP4 format bulunamadı.' })
    }

    // URL çözümleme: önce hazır URL, yoksa decipher
    let videoUrl = format.url
    if (!videoUrl && yt.session.player) {
      videoUrl = format.decipher(yt.session.player)
    }

    if (!videoUrl) {
      return res.status(500).json({ hata: 'Video URL\'i çözümlenemedi.' })
    }

    res.setHeader('Content-Disposition', `attachment; filename="${baslik}.mp4"`)
    return res.redirect(302, videoUrl)

  } catch (err) {
    console.error('[yt-indir]', err)
    return res.status(500).json({
      hata: 'Video işlenemedi.',
      detay: err.message,
    })
  }
}
