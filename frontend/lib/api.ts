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
 */
function getApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  
  // 🔍 디버깅: 환경변수 상태 로깅
  console.log('🔍 [API] NEXT_PUBLIC_API_URL:', url || '(미설정)');
  console.log('🔍 [API] NODE_ENV:', process.env.NODE_ENV);
  
  if (!url) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('⚠️ NEXT_PUBLIC_API_URL 미설정, localhost:8000 사용');
      return 'http://localhost:8000';
    }
    
    // 🚨 프로덕션에서 미설정 → 하드코딩 fallback
    console.error('❌ NEXT_PUBLIC_API_URL 환경변수가 설정되지 않았습니다!');
    console.warn('⚠️ Fallback: https://api.sajuqueen.com 사용');
    return 'https://api.sajuqueen.com';
  }
  
  return url;
}

const API_BASE_URL = getApiBaseUrl();

// 🔍 모듈 로드 시 URL 확인
console.log('✅ [API] Base URL 확정:', API_BASE_URL);

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
  
  const fullUrl = `${API_BASE_URL}${endpoint}`;
  
  // 🔍 디버깅: 실제 요청 URL 로깅
  console.log(`🚀 [API] ${method} ${fullUrl}`);
  
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(fullUrl, {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    
    // 🔍 디버깅: 응답 상태 로깅
    console.log(`📥 [API] Response: ${response.status} ${response.statusText}`);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error('❌ [API] Error response:', errorData);
      
      const errorMessage = 
        errorData.message || 
        errorData.detail?.message || 
        errorData.detail ||
        `서버 오류 (${response.status})`;
      throw new Error(errorMessage);
    }
    
    const data = await response.json();
    console.log('✅ [API] Success:', endpoint);
    return data;
    
  } catch (error) {
    clearTimeout(timeoutId);
    
    if (error instanceof Error) {
      console.error(`❌ [API] Error: ${error.message}`);
      
      if (error.name === 'AbortError') {
        throw new Error('서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.');
      }
      if (error.message.includes('fetch') || error.message.includes('Failed')) {
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
    { method: 'POST', body: data, timeout: 60000 }
  );
  
  // fallback 응답 체크 → 에러로 전환
  if (result.model_used === 'fallback') {
    console.error('❌ GPT API 호출 실패 - fallback 응답');
    throw new Error('AI 해석 서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.');
  }
  
  return result;
}

/**
 * 시간대 옵션 조회
 */
export async function getHourOptions(): Promise<HourOption[]> {
  return fetchWithTimeout<HourOption[]>(
    '/api/v1/calculate/hour-options',
    { timeout: 10000 }
  );
}

/**
 * 고민 유형 조회 (로컬 데이터)
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
