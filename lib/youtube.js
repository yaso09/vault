import { Innertube } from 'youtubei.js'

let instance = null

export async function getYT() {
  if (instance) return instance

  instance = await Innertube.create()

  const raw = process.env.YT_CREDENTIALS
  if (raw) {
    await instance.session.signIn(JSON.parse(raw))
    instance.session.on('update-credentials', ({ credentials }) => {
      console.log('Token yenilendi:', JSON.stringify(credentials))
    })
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
