'use client';

import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import ResultCard from '@/components/ResultCard';
import { getReportByJobIdAndToken } from '@/lib/api';

type PageStatus = 'loading' | 'generating' | 'completed' | 'error';

/**
 * 🔥 P0 수정: /report/{job_id}?token={token} 형식 지원
 * - URL path: job_id
 * - URL query: token
 */
export default function ReportPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  
  // 🔥 job_id는 path에서, token은 query에서
  const jobId = params.token as string;  // 폴더명이 [token]이지만 실제로는 job_id
  const token = searchParams.get('token');
  
  const [status, setStatus] = useState<PageStatus>('loading');
  const [reportData, setReportData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // 🔥 job_id와 token 둘 다 필요
    if (!jobId) {
      setError('잘못된 링크입니다 (job_id 없음)');
      setStatus('error');
      return;
    }
    
    if (!token) {
      setError('잘못된 링크입니다 (token 없음). 이메일의 링크를 다시 확인해주세요.');
      setStatus('error');
      return;
    }

    let pollingInterval: NodeJS.Timeout | null = null;

    const fetchReport = async () => {
      try {
        console.log(`[ReportPage] Fetching: jobId=${jobId}, token=${token.substring(0, 8)}...`);
        
        // 🔥 핵심: job_id + token으로 조회
        const data = await getReportByJobIdAndToken(jobId, token);
        
        console.log(`[ReportPage] Response: status=${data.status}, progress=${data.progress}`);
        
        if (data.status === 'completed' && data.result) {
          setReportData({
            calculateResult: data.result.legacy?.saju_data || {},
            interpretResult: data.result,
          });
          setStatus('completed');
        } else if (data.status === 'running' || data.status === 'pending') {
          setProgress(data.progress || 0);
          setStatus('generating');
          // 폴링 시작
          startPolling();
        } else if (data.status === 'failed') {
          setError(data.error || '리포트 생성에 실패했습니다');
          setStatus('error');
        }
      } catch (e) {
        console.error('[ReportPage] Error:', e);
        const errorMsg = e instanceof Error ? e.message : '리포트를 불러올 수 없습니다';
        
        // Invalid token 에러 처리
        if (errorMsg.includes('Invalid token') || errorMsg.includes('404')) {
          setError('유효하지 않은 링크입니다. 이메일의 링크를 다시 확인해주세요.');
        } else {
          setError(errorMsg);
        }
        setStatus('error');
      }
    };

    const startPolling = () => {
      if (pollingInterval) return;
      
      pollingInterval = setInterval(async () => {
        try {
          const data = await getReportByJobIdAndToken(jobId, token);
          
          if (data.status === 'completed' && data.result) {
            if (pollingInterval) clearInterval(pollingInterval);
            setReportData({
              calculateResult: data.result.legacy?.saju_data || {},
              interpretResult: data.result,
            });
            setStatus('completed');
          } else if (data.status === 'failed') {
            if (pollingInterval) clearInterval(pollingInterval);
            setError(data.error || '리포트 생성에 실패했습니다');
            setStatus('error');
          } else {
            setProgress(data.progress || 0);
          }
        } catch (e) {
          // 폴링 에러는 무시 (네트워크 일시 오류 등)
          console.warn('[ReportPage] Polling error (ignored):', e);
        }
      }, 3000);
    };

    fetchReport();

    return () => {
      if (pollingInterval) clearInterval(pollingInterval);
    };
  }, [jobId, token]);

  const BRAND_NAME = process.env.NEXT_PUBLIC_BRAND_NAME ?? '사주OS';

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-purple-50 py-8">
      <div className="container mx-auto px-4 max-w-4xl">
        {/* Header */}
        <header className="text-center py-6">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-600 to-amber-500 bg-clip-text text-transparent">
            🔮 {BRAND_NAME}
          </h1>
          <p className="text-slate-600 mt-2">프리미엄 비즈니스 컨설팅 보고서</p>
        </header>

        {/* Loading */}
        {status === 'loading' && (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mb-6" />
            <p className="text-slate-600">보고서를 불러오는 중...</p>
          </div>
        )}

        {/* Generating */}
        {status === 'generating' && (
          <div className="bg-white rounded-2xl shadow-lg p-8 animate-fade-in-up">
            <div className="text-center mb-6">
              <div className="text-4xl mb-3">⏳</div>
              <h2 className="text-xl font-bold text-gray-800">보고서 생성 중입니다</h2>
              <p className="text-gray-600 mt-2">
                잠시만 기다려주세요. 완료되면 자동으로 표시됩니다.
              </p>
            </div>

            <div className="max-w-md mx-auto">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600">진행률</span>
                <span className="text-sm font-bold text-purple-600">{progress}%</span>
              </div>
              <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-600 to-amber-500 rounded-full transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            <div className="mt-8 p-4 bg-purple-50 rounded-xl text-center">
              <p className="text-sm text-gray-600">
                💡 이 페이지를 북마크해두시면 언제든 다시 확인하실 수 있어요.
              </p>
            </div>
          </div>
        )}

        {/* Error */}
        {status === 'error' && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-8 text-center">
            <div className="text-4xl mb-3">⚠️</div>
            <h2 className="text-xl font-bold text-red-700">오류가 발생했습니다</h2>
            <p className="text-red-600 mt-2">{error}</p>
            <div className="mt-6 space-x-4">
              <button
                onClick={() => window.location.reload()}
                className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
              >
                다시 시도
              </button>
              <button
                onClick={() => window.location.href = '/'}
                className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
              >
                홈으로
              </button>
            </div>
          </div>
        )}

        {/* Completed */}
        {status === 'completed' && reportData && (
          <ResultCard
            calculateResult={reportData.calculateResult}
            interpretResult={reportData.interpretResult}
            onReset={() => window.location.href = '/'}
          />
        )}

        {/* Footer */}
        <footer className="text-center py-8 text-sm text-gray-500">
          <p>© 2025 {BRAND_NAME}. All rights reserved.</p>
          <p className="mt-1">문의: support@sajuos.com</p>
        </footer>
      </div>
    </div>
  );
}
