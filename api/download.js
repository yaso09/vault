import { getYT, videoIdCikar } from '../lib/youtube.js'

export default async function handler(req, res) {
  const { url, kalite = '720' } = req.query
  const videoId = videoIdCikar(url)
  if (!videoId) return res.status(400).json({ hata: 'Geçersiz URL.' })

  try {
    const yt = await getYT()
    const bilgi = await yt.getInfo(videoId)

    const tumFormatlar = [
      ...(bilgi.streaming_data?.formats ?? []),
      ...(bilgi.streaming_data?.adaptive_formats ?? []),
    ]

    const format =
      tumFormatlar
        .filter(f =>
          f.has_video && f.has_audio &&
          f.mime_type?.includes('video/mp4') &&
          (f.height ?? 0) <= parseInt(kalite)
        )
        .sort((a, b) => (b.height ?? 0) - (a.height ?? 0))[0]
      ??
      tumFormatlar
        .filter(f => f.has_video && f.mime_type?.includes('video/mp4'))
        .sort((a, b) => (b.height ?? 0) - (a.height ?? 0))[0]

    if (!format) return res.status(404).json({ hata: 'Format bulunamadı.' })

    const videoUrl = format.url ?? format.decipher(yt.session.player)
    if (!videoUrl) return res.status(500).json({ hata: 'URL çözümlenemedi.' })

    res.setHeader('Content-Disposition', 'attachment; filename="video.mp4"')
    return res.redirect(302, videoUrl)
  } catch (err) {
    return res.status(500).json({ hata: err.message })
  }
}
