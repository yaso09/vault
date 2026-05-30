import { Innertube } from 'youtubei.js'

let instance = null

export async function getYT() {
  if (instance) return instance

  instance = await Innertube.create({
    generate_session_locally: true,
    retrieve_player: true,
  })

  const raw = process.env.YT_CREDENTIALS
  if (raw) {
    try {
      await instance.session.signIn(JSON.parse(raw))
      instance.session.on('update-credentials', ({ credentials }) => {
        console.log('Token yenilendi:', JSON.stringify(credentials))
      })
    } catch (err) {
      console.warn('OAuth girişi başarısız:', err.message)
    }
  }

  return instance
}

export function videoIdCikar(url) {
  try {
    const u = new URL(url)
    if (u.hostname === 'youtu.be') return u.pathname.slice(1).split('?')[0]
    return u.searchParams.get('v')
  } catch { return null }
}

export function formatUrlCoz(format, player) {
  // Önce hazır URL, sonra decipher, ikisi de yoksa null
  try {
    if (format.url) return format.url
    if (player) return format.decipher(player)
  } catch {
    return null
  }
  return null
}
