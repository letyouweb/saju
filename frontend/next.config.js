/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // 🔥 P0: Vercel 배포 시 Railway 공개 URL 사용
    const backendUrl = process.env.BACKEND_URL || 'https://saju-production-6438.up.railway.app'
    
    console.log(`[Next.js] Rewrites destination: ${backendUrl}`)
    
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`
      }
    ]
  }
}

module.exports = nextConfig
