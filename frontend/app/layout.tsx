import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI 사주 - 당신의 운명을 읽다',
  description: '인공지능이 분석하는 정확한 사주풀이. 연애운, 재물운, 직업운을 지금 바로 확인하세요.',
  keywords: ['사주', '운세', '명리학', 'AI', '인공지능', '팔자', '사주풀이'],
  openGraph: {
    title: 'AI 사주 - 당신의 운명을 읽다',
    description: '인공지능이 분석하는 정확한 사주풀이',
    type: 'website',
    locale: 'ko_KR',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <head>
        <link
          rel="stylesheet"
          as="style"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
        />
      </head>
      <body className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-amber-50">
        <main className="container mx-auto px-4 py-8 max-w-4xl">
          {children}
        </main>
        
        {/* Footer */}
        <footer className="text-center py-8 text-gray-500 text-sm">
          <p className="mb-2">
            ⚠️ 본 서비스는 오락/참고 목적으로 제공되며, 의학/법률/투자 등 전문적 조언을 대체하지 않습니다.
          </p>
          <p>© 2025 AI 사주. All rights reserved.</p>
        </footer>
      </body>
    </html>
  );
}
