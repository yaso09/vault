import { getYT, videoIdCikar } from '../lib/youtube.js'

export default async function handler(req, res) {
  const { url } = req.query
  const videoId = videoIdCikar(url)
  if (!videoId) return res.status(400).json({ hata: 'Geçersiz URL.' })

  try {
    const yt = await getYT()
    const bilgi = await yt.getInfo(videoId)

    const formatlar = [
      ...(bilgi.streaming_data?.formats ?? []),
      ...(bilgi.streaming_data?.adaptive_formats ?? []),
    ]
      .filter(f => f.has_video && f.has_audio && f.mime_type?.includes('video/mp4'))
      .map(f => ({ kalite: `${f.height}p`, height: f.height }))
      .filter(f => f.height)
      .sort((a, b) => b.height - a.height)

    return res.json({
      baslik: bilgi.basic_info.title,
      thumbnail: bilgi.basic_info.thumbnail?.[0]?.url,
      sure: bilgi.basic_info.duration,
      formatlar,
    })
  } catch (err) {
    return res.status(500).json({ hata: err.message })
  }
}
