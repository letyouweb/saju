/**
 * API 통신 함수 - Railway 백엔드 직접 호출
 * 
 * 아키텍처:
 * - Vercel (프론트엔드) → Railway (백엔드) 직접 통신
 * - Vercel API Routes 사용 안 함 (보안/효율성)
 * - CORS: Railway에서 sajuqueen.com 허용 필수
 */

import type {
  CalculateRequest,
  CalculateResponse,
  InterpretRequest,
  InterpretResponse,
  HourOption,
} from '@/types';

// ============ 환경변수 검증 ============

/**
 * API Base URL 가져오기 (타입 안전)
 * - 환경변수 없으면 런타임 에러 방지
 */
function getApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  
  if (!url) {
    // 개발 환경에서는 localhost 사용
    if (process.env.NODE_ENV === 'development') {
      console.warn('⚠️ NEXT_PUBLIC_API_URL 미설정, localhost:8000 사용');
      return 'http://localhost:8000';
    }
    
    // 프로덕션에서 미설정이면 에러
    console.error('❌ NEXT_PUBLIC_API_URL 환경변수가 설정되지 않았습니다!');
    throw new Error('API 서버 주소가 설정되지 않았습니다. 관리자에게 문의하세요.');
  }
  
  return url;
}

const API_BASE_URL = getApiBaseUrl();

// ============ 공통 Fetch 함수 ============

interface FetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  timeout?: number;
}

/**
 * 타임아웃 지원 fetch 래퍼
 */
async function fetchWithTimeout<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const { method = 'GET', body, timeout = 30000 } = options;
  
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = 
        errorData.message || 
        errorData.detail?.message || 
        errorData.detail ||
        `서버 오류 (${response.status})`;
      throw new Error(errorMessage);
    }
    
    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    
    if (error instanceof Error) {
      // 타임아웃
      if (error.name === 'AbortError') {
        throw new Error('서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.');
      }
      // 네트워크 에러
      if (error.message.includes('fetch')) {
        throw new Error('서버에 연결할 수 없습니다. 네트워크 연결을 확인해주세요.');
      }
      throw error;
    }
    
    throw new Error('알 수 없는 오류가 발생했습니다.');
  }
}

// ============ API 함수들 ============

/**
 * 사주 계산 API
 * POST /api/v1/calculate
 */
export async function calculateSaju(
  data: CalculateRequest
): Promise<CalculateResponse> {
  const result = await fetchWithTimeout<CalculateResponse>(
    '/api/v1/calculate',
    { method: 'POST', body: data, timeout: 15000 }
  );
  
  // fallback 결과 경고 (에러는 아님)
  if (result.calculation_method === 'fallback') {
    console.warn('⚠️ Fallback 계산 사용됨');
  }
  
  return result;
}

/**
 * 사주 해석 API
 * POST /api/v1/interpret
 */
export async function interpretSaju(
  data: InterpretRequest
): Promise<InterpretResponse> {
  const result = await fetchWithTimeout<InterpretResponse>(
    '/api/v1/interpret',
    { method: 'POST', body: data, timeout: 60000 } // GPT 응답 대기 (최대 60초)
  );
  
  // fallback 응답 체크
  if (result.model_used === 'fallback') {
    throw new Error('AI 해석 서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.');
  }
  
  return result;
}

/**
 * 시간대 옵션 조회
 * GET /api/v1/calculate/hour-options
 */
export async function getHourOptions(): Promise<HourOption[]> {
  return fetchWithTimeout<HourOption[]>(
    '/api/v1/calculate/hour-options',
    { timeout: 10000 }
  );
}

/**
 * 고민 유형 조회 (로컬 데이터 - 백엔드 호출 안 함)
 */
export function getConcernTypes(): {
  concern_types: Array<{ value: string; label: string; emoji: string }>;
} {
  return {
    concern_types: [
      { value: 'love', label: '연애/결혼', emoji: '💕' },
      { value: 'wealth', label: '재물/금전', emoji: '💰' },
      { value: 'career', label: '직장/사업', emoji: '💼' },
      { value: 'health', label: '건강', emoji: '🏥' },
      { value: 'study', label: '학업/시험', emoji: '📚' },
      { value: 'general', label: '종합/기타', emoji: '🔮' },
    ]
  };
}

/**
 * 헬스체크
 * GET /health
 */
export async function healthCheck(): Promise<{ status: string }> {
  return fetchWithTimeout<{ status: string }>(
    '/health',
    { timeout: 5000 }
  );
}

/**
 * API 연결 테스트 (디버깅용)
 */
export async function testConnection(): Promise<{
  success: boolean;
  apiUrl: string;
  error?: string;
}> {
  try {
    await healthCheck();
    return { success: true, apiUrl: API_BASE_URL };
  } catch (error) {
    return {
      success: false,
      apiUrl: API_BASE_URL,
      error: error instanceof Error ? error.message : '알 수 없는 오류'
    };
  }
}
