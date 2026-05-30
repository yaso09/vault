export default async function handler(req, res) {
  const { url } = req.query

  if (!url) return res.status(400).json({ hata: 'URL eksik.' })

  try {
    const cobalt = await fetch('https://api.cobalt.tools/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        url,
        videoQuality: '720',
        filenameStyle: 'basic',
        downloadMode: 'auto',
      }),
      signal: AbortSignal.timeout(10000),
    })

    const data = await cobalt.json()

    // status: "redirect" → direkt URL
    // status: "tunnel"   → cobalt proxy URL
    // status: "picker"   → birden fazla seçenek (playlist vb.)
    if (data.status === 'redirect' || data.status === 'tunnel') {
      res.setHeader('Content-Disposition', 'attachment; filename="video.mp4"')
      return res.redirect(302, data.url)
    }

    if (data.status === 'picker') {
      // İlk öğeyi al
      const ilk = data.picker?.[0]?.url
      if (ilk) {
        res.setHeader('Content-Disposition', 'attachment; filename="video.mp4"')
        return res.redirect(302, ilk)
      }
    }

    return res.status(400).json({ hata: data.error?.code ?? 'Bilinmeyen hata.', ham: data })

  } catch (err) {
    return res.status(500).json({ hata: err.message })
  }
}
