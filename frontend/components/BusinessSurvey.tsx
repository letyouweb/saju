'use client';

import { useState } from 'react';

// 설문 선택지 정의
const BUSINESS_STAGES = [
  { value: 'idea', label: '🌱 아이디어/기획 단계' },
  { value: '0to1', label: '🚀 0→1 (첫 매출 전)' },
  { value: '1to10', label: '📈 1→10 (성장 초기)' },
  { value: '10to100', label: '🏗️ 10→100 (확장 단계)' },
  { value: 'established', label: '🏢 안정기 (연매출 10억+)' },
  { value: 'pivot', label: '🔄 사업 전환/피봇' },
];

const REVENUE_RANGES = [
  { value: '0', label: '매출 없음' },
  { value: 'under_500', label: '500만원 미만' },
  { value: '500_1000', label: '500~1000만원' },
  { value: '1000_3000', label: '1000~3000만원' },
  { value: '3000_5000', label: '3000~5000만원' },
  { value: '5000_1b', label: '5000만원~1억' },
  { value: 'over_1b', label: '1억 이상' },
];

const CASH_RESERVES = [
  { value: '0', label: '없음' },
  { value: 'under_1000', label: '1000만원 미만' },
  { value: '1000_5000', label: '1000~5000만원' },
  { value: '5000_1b', label: '5000만원~1억' },
  { value: '1b_3b', label: '1~3억' },
  { value: 'over_3b', label: '3억 이상' },
];

const BOTTLENECKS = [
  { value: 'lead', label: '🎯 리드/고객 확보', desc: '잠재 고객이 부족' },
  { value: 'conversion', label: '💰 전환율', desc: '관심→구매 전환이 낮음' },
  { value: 'operations', label: '⚙️ 운영/시스템', desc: '업무 효율이 낮음' },
  { value: 'team', label: '👥 팀/인력', desc: '사람이 부족하거나 역량 부족' },
  { value: 'funding', label: '💸 자금/캐시플로우', desc: '돈이 부족' },
  { value: 'mental', label: '🧠 멘탈/번아웃', desc: '체력/의욕 저하' },
  { value: 'direction', label: '🧭 방향성/전략', desc: '무엇을 해야 할지 모르겠음' },
  { value: 'competition', label: '⚔️ 경쟁/차별화', desc: '경쟁자 대비 우위가 없음' },
];

const TIME_OPTIONS = [
  { value: 'under_10', label: '10시간 미만 (부업)' },
  { value: '10_30', label: '10~30시간 (파트타임)' },
  { value: '30_50', label: '30~50시간 (풀타임)' },
  { value: 'over_50', label: '50시간+ (올인)' },
];

const RISK_OPTIONS = [
  { value: 'conservative', label: '🛡️ 보수적', desc: '안정 최우선, 리스크 최소화' },
  { value: 'balanced', label: '⚖️ 중립', desc: '성장과 안정 균형' },
  { value: 'aggressive', label: '🚀 공격적', desc: '고위험 고수익 추구' },
];

export interface SurveyData {
  industry: string;
  business_stage: string;
  monthly_revenue: string;
  margin_percent: number;
  cash_reserve: string;
  primary_bottleneck: string;
  goal_detail: string;
  time_availability: string;
  risk_tolerance: string;
  urgent_question: string;
}

interface SurveyFormProps {
  onComplete: (data: SurveyData) => void;
  onSkip?: () => void;
}

export default function SurveyForm({ onComplete, onSkip }: SurveyFormProps) {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState<SurveyData>({
    industry: '',
    business_stage: '1to10',
    monthly_revenue: 'under_1000',
    margin_percent: 30,
    cash_reserve: 'under_1000',
    primary_bottleneck: 'lead',
    goal_detail: '',
    time_availability: '30_50',
    risk_tolerance: 'balanced',
    urgent_question: '',
  });

  const totalSteps = 4;

  const updateField = (field: keyof SurveyData, value: string | number) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleNext = () => {
    if (step < totalSteps) {
      setStep(step + 1);
    } else {
      onComplete(formData);
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const isStepValid = () => {
    switch (step) {
      case 1: return formData.industry.length >= 2;
      case 2: return true; // 선택지는 기본값이 있음
      case 3: return formData.goal_detail.length >= 5;
      case 4: return true;
      default: return true;
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 md:p-8 animate-fade-in-up">
      {/* 헤더 */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
            <span>📋</span> 맞춤 컨설팅을 위한 60초 설문
          </h2>
          <span className="text-sm text-purple-600 font-medium">
            {step}/{totalSteps}
          </span>
        </div>
        
        {/* 프로그레스 바 */}
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-purple-500 to-purple-600 transition-all duration-300"
            style={{ width: `${(step / totalSteps) * 100}%` }}
          />
        </div>
        
        <p className="text-sm text-gray-500 mt-2">
          이 정보로 일반론이 아닌 <strong>당신 상황에 맞는 전략</strong>을 제공합니다.
        </p>
      </div>

      {/* Step 1: 업종 + 사업 단계 */}
      {step === 1 && (
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              업종/사업 분야 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.industry}
              onChange={e => updateField('industry', e.target.value)}
              placeholder="예: IT/SaaS, 온라인 커머스, 교육, 컨설팅..."
              className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              현재 사업 단계
            </label>
            <div className="grid grid-cols-2 gap-2">
              {BUSINESS_STAGES.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => updateField('business_stage', option.value)}
                  className={`p-3 rounded-lg border-2 text-sm text-left transition ${
                    formData.business_stage === option.value
                      ? 'border-purple-500 bg-purple-50 text-purple-700'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Step 2: 재무 현황 */}
      {step === 2 && (
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              현재 월매출
            </label>
            <select
              value={formData.monthly_revenue}
              onChange={e => updateField('monthly_revenue', e.target.value)}
              className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500"
            >
              {REVENUE_RANGES.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              평균 마진율: {formData.margin_percent}%
            </label>
            <input
              type="range"
              min="0"
              max="100"
              value={formData.margin_percent}
              onChange={e => updateField('margin_percent', parseInt(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              현금 보유량 (비상금)
            </label>
            <select
              value={formData.cash_reserve}
              onChange={e => updateField('cash_reserve', e.target.value)}
              className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500"
            >
              {CASH_RESERVES.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Step 3: 목표 + 병목 */}
      {step === 3 && (
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              2026년 가장 중요한 목표 1개 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.goal_detail}
              onChange={e => updateField('goal_detail', e.target.value)}
              placeholder="예: 월매출 5000만원, 팀 3명 채용, 브랜드 인지도 확보..."
              className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              지금 가장 큰 병목은?
            </label>
            <div className="grid grid-cols-2 gap-2">
              {BOTTLENECKS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => updateField('primary_bottleneck', option.value)}
                  className={`p-3 rounded-lg border-2 text-left transition ${
                    formData.primary_bottleneck === option.value
                      ? 'border-purple-500 bg-purple-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="font-medium text-sm">{option.label}</div>
                  <div className="text-xs text-gray-500 mt-1">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Step 4: 시간 + 리스크 + 추가 질문 */}
      {step === 4 && (
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              주당 투입 가능 시간
            </label>
            <div className="grid grid-cols-2 gap-2">
              {TIME_OPTIONS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => updateField('time_availability', option.value)}
                  className={`p-3 rounded-lg border-2 text-sm transition ${
                    formData.time_availability === option.value
                      ? 'border-purple-500 bg-purple-50 text-purple-700'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              리스크 성향
            </label>
            <div className="grid grid-cols-3 gap-2">
              {RISK_OPTIONS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => updateField('risk_tolerance', option.value)}
                  className={`p-3 rounded-lg border-2 text-center transition ${
                    formData.risk_tolerance === option.value
                      ? 'border-purple-500 bg-purple-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="font-medium text-sm">{option.label}</div>
                  <div className="text-xs text-gray-500 mt-1">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              지금 당장 해결하고 싶은 질문 (선택)
            </label>
            <textarea
              value={formData.urgent_question}
              onChange={e => updateField('urgent_question', e.target.value)}
              placeholder="예: 첫 고객을 어떻게 확보할까요? 가격 책정은 어떻게?"
              rows={3}
              className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 resize-none"
            />
          </div>
        </div>
      )}

      {/* 버튼 */}
      <div className="flex items-center justify-between mt-8">
        <div>
          {step > 1 ? (
            <button
              type="button"
              onClick={handleBack}
              className="px-4 py-2 text-gray-600 hover:text-gray-800 transition"
            >
              ← 이전
            </button>
          ) : onSkip ? (
            <button
              type="button"
              onClick={onSkip}
              className="px-4 py-2 text-gray-500 hover:text-gray-700 text-sm"
            >
              건너뛰기
            </button>
          ) : null}
        </div>

        <button
          type="button"
          onClick={handleNext}
          disabled={!isStepValid()}
          className={`px-6 py-3 rounded-lg font-medium transition ${
            isStepValid()
              ? 'bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }`}
        >
          {step < totalSteps ? '다음 →' : '설문 완료 ✓'}
        </button>
      </div>

      {/* 안내 문구 */}
      <div className="mt-4 p-3 bg-blue-50 rounded-lg">
        <p className="text-xs text-blue-700">
          💡 이 정보는 보고서 생성에만 사용되며, 외부에 공유되지 않습니다.
        </p>
      </div>
    </div>
  );
}
