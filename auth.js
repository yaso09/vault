// auth.js
import { Innertube } from 'youtubei.js'

const yt = await Innertube.create()

yt.session.on('auth-pending', (data) => {
  console.log('\n→ Bu adrese git:', data.verification_url)
  console.log('→ Bu kodu gir :', data.user_code)
})

yt.session.on('auth', ({ credentials }) => {
  console.log('\n✓ Giriş başarılı! Şu değeri kopyala:\n')
  console.log(JSON.stringify(credentials))
})

await yt.session.signIn()
await new Promise(() => {}) // giriş tamamlanana kadar bekle
