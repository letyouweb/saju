'use client';

import { useState } from 'react';
import SajuForm from '@/components/SajuForm';
import ResultCard from '@/components/ResultCard';
import type { CalculateResponse, InterpretResponse, ConcernType } from '@/types';
import { calculateSaju, interpretSaju } from '@/lib/api';

export default function Home() {
  const [step, setStep] = useState<'input' | 'loading' | 'result'>('input');
  const [calculateResult, setCalculateResult] = useState<CalculateResponse | null>(null);
  const [interpretResult, setInterpretResult] = useState<InterpretResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (formData: {
    name: string;
    birthYear: number;
    birthMonth: number;
    birthDay: number;
    birthHour: number | null;
    birthMinute: number;
    gender: 'male' | 'female' | 'other';
    concernType: ConcernType;
    question: string;
  }) => {
    setStep('loading');
    setError(null);

    try {
      // 1. 사주 계산 (절기 기반)
      const calcResult = await calculateSaju({
        birth_year: formData.birthYear,
        birth_month: formData.birthMonth,
        birth_day: formData.birthDay,
        birth_hour: formData.birthHour,
        birth_minute: formData.birthMinute,
        gender: formData.gender,
      });
      setCalculateResult(calcResult);

      // 2. 사주 해석
      const interpResult = await interpretSaju({
        saju_result: calcResult,
        name: formData.name,
        gender: formData.gender,
        concern_type: formData.concernType,
        question: formData.question,
      });
      setInterpretResult(interpResult);

      setStep('result');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.';
      setError(errorMessage);
      setStep('input');
    }
  };

  const handleReset = () => {
    setStep('input');
    setCalculateResult(null);
    setInterpretResult(null);
    setError(null);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <header className="text-center py-8">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-amber-500 bg-clip-text text-transparent mb-3">
          🔮 AI 사주
        </h1>
        <p className="text-gray-600 text-lg">
          인공지능이 분석하는 당신의 운명
        </p>
        <p className="text-sm text-gray-400 mt-2">
          절기 기준 정밀 계산 · 2시간 단위 시주 분석
        </p>
      </header>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg animate-fade-in-up">
          <div className="flex items-start gap-3">
            <span className="text-xl">⚠️</span>
            <div>
              <p className="font-medium">오류 발생</p>
              <p className="text-sm mt-1">{error}</p>
              <p className="text-xs text-red-500 mt-2">
                네트워크 연결과 서버 상태를 확인해주세요.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Step: Input Form */}
      {step === 'input' && <SajuForm onSubmit={handleSubmit} />}

      {/* Step: Loading */}
      {step === 'loading' && (
        <div className="flex flex-col items-center justify-center py-20 animate-fade-in-up">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mb-6" />
          <p className="text-xl font-medium text-gray-700">사주를 분석중입니다...</p>
          <p className="text-gray-500 mt-2">절기 기준으로 정밀 계산 중 🌟</p>
          <div className="mt-4 text-sm text-gray-400">
            <p>• 연주: 입춘 기준 보정</p>
            <p>• 월주: 절기(입절) 기준 계산</p>
            <p>• 시주: 2시간 단위 범위 적용</p>
          </div>
        </div>
      )}

      {/* Step: Result */}
      {step === 'result' && calculateResult && interpretResult && (
        <ResultCard
          calculateResult={calculateResult}
          interpretResult={interpretResult}
          onReset={handleReset}
        />
      )}
    </div>
  );
}
