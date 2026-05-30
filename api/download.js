import ytdl from '@distube/ytdl-core'

export default async function handler(req, res) {
  const { url } = req.query

  if (!url || !ytdl.validateURL(url)) {
    return res.status(400).json({ hata: 'Geçerli bir YouTube URL\'i giriniz.' })
  }

  try {
    const bilgi = await ytdl.getInfo(url)

    // Ses + video birleşik formatları filtrele (mp4)
    const formatlar = bilgi.formats.filter(
      (f) => f.hasVideo && f.hasAudio && f.container === 'mp4'
    )

    if (formatlar.length === 0) {
      return res.status(404).json({ hata: 'Uygun MP4 formatı bulunamadı.' })
    }

    // En yüksek kaliteliyi seç
    const format = formatlar.sort((a, b) => (b.height ?? 0) - (a.height ?? 0))[0]
    const baslik = bilgi.videoDetails.title.replace(/[^\w\s]/gi, '').trim()

    // Doğrudan YouTube CDN'ine yönlendir
    res.setHeader('Content-Disposition', `attachment; filename="${baslik}.mp4"`)
    return res.redirect(302, format.url)

  } catch (err) {
    return res.status(500).json({ hata: 'Video işlenemedi.', detay: err.message })
  }
}
