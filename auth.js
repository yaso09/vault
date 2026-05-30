import { Innertube } from 'youtubei.js'

const yt = await Innertube.create()

yt.session.on('auth-pending', ({ verification_url, user_code }) => {
  console.log('\n1. Şu adrese git :', verification_url)
  console.log('2. Bu kodu gir   :', user_code)
})

yt.session.on('auth', ({ credentials }) => {
  console.log('\n✓ Başarılı! Vercel\'e ekleyeceğin değer:\n')
  console.log(JSON.stringify(credentials))
  process.exit(0)
})

await yt.session.signIn()
