async function calisanInstanceBul() {
  try {
    const res = await fetch('https://instances.cobalt.best/api', {
      signal: AbortSignal.timeout(5000)
    })
    const liste = await res.json()

    // Auth gerektirmeyen, online, YouTube destekleyen instance'ı bul
    const uygun = liste.find(
      (i) => i.online && i.info?.auth === false && i.services?.youtube === true
    )

    return uygun ? `https://${uygun.api}` : null
  } catch {
    return null
  }
}

export default async function handler(req, res) {
  const { url } = req.query
  if (!url) return res.status(400).json({ hata: 'URL eksik.' })

  const instance = await calisanInstanceBul()
  if (!instance) {
    return res.status(503).json({ hata: 'Uygun Cobalt instance bulunamadı.' })
  }

  try {
    const cobalt = await fetch(`${instance}/`, {
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

    if (data.status === 'redirect' || data.status === 'tunnel') {
      res.setHeader('Content-Disposition', 'attachment; filename="video.mp4"')
      return res.redirect(302, data.url)
    }

    if (data.status === 'picker') {
      const ilk = data.picker?.[0]?.url
      if (ilk) {
        res.setHeader('Content-Disposition', 'attachment; filename="video.mp4"')
        return res.redirect(302, ilk)
      }
    }

    return res.status(400).json({ hata: data.error?.code ?? 'Bilinmeyen hata.', instance })
  } catch (err) {
    return res.status(500).json({ hata: err.message, instance })
  }
}
