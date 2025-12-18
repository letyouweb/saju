import type { Metadata } from 'next';
import './globals.css';

const BRAND_NAME = process.env.NEXT_PUBLIC_BRAND_NAME ?? '사주퀸';
const BRAND_DESC =
  process.env.NEXT_PUBLIC_BRAND_DESC ??
  '만세력 기반으로 사주 원국을 정리하고, 질문에 맞게 해석해 드려요.';

export const metadata: Metadata = {
  title: `${BRAND_NAME} - 사주 원국 해석`,
  description: BRAND_DESC,
  keywords: ['사주', '운세', '명리학', 'AI', '인공지능', '팔자', '사주풀이', '만세력'],
  openGraph: {
    title: `${BRAND_NAME} - 사주 원국 해석`,
    description: BRAND_DESC,
    type: 'website',
    locale: 'ko_KR',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const year = new Date().getFullYear();
  
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
      <body className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-amber-50 text-slate-900 antialiased">
        <main className="container mx-auto px-4 py-8 max-w-4xl">
          {children}
        </main>
        
        {/* Footer */}
        <footer className="text-center py-8 text-slate-500 text-sm">
          <p className="mb-2">
            ⚠️ 본 서비스는 오락/참고 목적으로 제공되며, 의학/법률/투자 등 전문적 조언을 대체하지 않습니다.
          </p>
          <p>© {year} {BRAND_NAME}. All rights reserved.</p>
        </footer>
      </body>
    </html>
  );
}
