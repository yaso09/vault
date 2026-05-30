import { Innertube } from 'youtubei.js'

export default async function handler(req, res) {
  const { url } = req.query

  if (!url) {
    return res.status(400).json({ hata: 'URL parametresi eksik.' })
  }

  // Video ID'yi URL'den çıkar
  const match = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/)
  if (!match) {
    return res.status(400).json({ hata: 'Geçerli bir YouTube URL\'i giriniz.' })
  }

  const videoId = match[1]

  try {
    const yt = await Innertube.create({ retrieve_player: true })
    const bilgi = await yt.getBasicInfo(videoId)

    const baslik = bilgi.basic_info.title?.replace(/[^\w\s]/gi, '').trim() ?? videoId

    // Ses + video birleşik MP4 formatlarını filtrele
    const formatlar = bilgi.streaming_data?.formats ?? []
    const mp4Formatlar = formatlar
      .filter((f) => f.mime_type?.startsWith('video/mp4'))
      .sort((a, b) => (b.height ?? 0) - (a.height ?? 0))

    if (mp4Formatlar.length === 0) {
      return res.status(404).json({ hata: 'Uygun MP4 formatı bulunamadı.' })
    }

    const format = mp4Formatlar[0]
    const videoUrl = format.decipher(yt.session.player)

    res.setHeader('Content-Disposition', `attachment; filename="${baslik}.mp4"`)
    return res.redirect(302, videoUrl)

  } catch (err) {
    return res.status(500).json({ hata: 'Video işlenemedi.', detay: err.message })
  }
}
