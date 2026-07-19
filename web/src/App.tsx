import { useEffect, useState } from 'react'
import HeroFuturistic from '@/components/ui/hero-futuristic'
import AetherFlowHero from '@/components/ui/aether-flow-hero'

function App() {
  const [hash, setHash] = useState(window.location.hash)

  useEffect(() => {
    const onHash = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  if (hash === '#aether') return <AetherFlowHero />
  return <HeroFuturistic />
}

export default App
