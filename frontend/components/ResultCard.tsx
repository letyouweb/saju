'use client';

import { useState } from 'react';
import type { CalculateResponse, InterpretResponse } from '@/types';
import { getAccuracyBadge, getAccuracyBadgeInfo, HOUR_OPTIONS } from '@/types';

interface ResultCardProps {
  calculateResult: CalculateResponse;
  interpretResult: InterpretResponse;
  onReset: () => void;
}

export default function ResultCard({
  calculateResult,
  interpretResult,
  onReset,
}: ResultCardProps) {
  const [activeTab, setActiveTab] = useState<'summary' | 'detail' | 'action'>('summary');
  const [showBoundaryModal, setShowBoundaryModal] = useState(false);

  // 정확도 배지 계산
  const accuracyBadge = getAccuracyBadge(calculateResult.quality);
  const badgeInfo = getAccuracyBadgeInfo(accuracyBadge);

  const handleShare = async () => {
    // 경계일이면 경고 모달
    if (calculateResult.quality.solar_term_boundary) {
      setShowBoundaryModal(true);
      return;
    }
    
    await doShare();
  };

  const doShare = async () => {
    const shareText = `🔮 AI 사주 결과\n\n${interpretResult.summary}\n\n✨ ${interpretResult.blessing}`;
    
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'AI 사주 결과',
          text: shareText,
        });
      } catch (err) {
        // 사용자가 공유 취소한 경우
      }
    } else {
      await navigator.clipboard.writeText(shareText);
      alert('결과가 클립보드에 복사되었습니다!');
    }
  };

  // 시주 시간 범위 표시
  const getHourRange = (jiIndex: number | undefined) => {
    if (jiIndex === undefined) return '';
    const option = HOUR_OPTIONS[jiIndex];
    return option ? `${option.range_start}~${option.range_end}` : '';
  };

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* 정확도 배지 (상단) */}
      <div className={`flex items-center justify-between p-4 rounded-xl ${
        accuracyBadge === 'high' ? 'bg-green-50 border border-green-200' :
        accuracyBadge === 'boundary' ? 'bg-yellow-50 border border-yellow-200' :
        'bg-blue-50 border border-blue-200'
      }`}>
        <div className="flex items-center gap-2">
          <span className="text-2xl">{badgeInfo.icon}</span>
          <div>
            <p className={`font-bold ${
              accuracyBadge === 'high' ? 'text-green-700' :
              accuracyBadge === 'boundary' ? 'text-yellow-700' :
              'text-blue-700'
            }`}>
              {badgeInfo.label}
            </p>
            <p className="text-xs text-gray-600">{badgeInfo.tooltip}</p>
          </div>
        </div>
      </div>

      {/* 사주 원국 카드 */}
      <div className="bg-white rounded-2xl shadow-lg overflow-hidden result-card">
        <div className="gradient-bg text-white p-6">
          <h2 className="text-2xl font-bold mb-2">📜 사주 원국</h2>
          <p className="opacity-90">{calculateResult.birth_info}</p>
        </div>
        
        <div className="p-6">
          {/* 4기둥 표시 (개선: 천간/지지/오행 분리) */}
          <div className="grid grid-cols-4 gap-2 mb-6">
            {[
              { label: '시주', pillar: calculateResult.saju.hour_pillar, hanja: '時' },
              { label: '일주', pillar: calculateResult.saju.day_pillar, hanja: '日' },
              { label: '월주', pillar: calculateResult.saju.month_pillar, hanja: '月' },
              { label: '년주', pillar: calculateResult.saju.year_pillar, hanja: '年' },
            ].map((item, idx) => (
              <div key={item.label} className="text-center">
                <p className="text-xs text-gray-500 mb-1">{item.label}({item.hanja})</p>
                <div className="bg-gradient-to-b from-amber-50 to-amber-100 rounded-lg p-3 border border-amber-200">
                  {item.pillar ? (
                    <>
                      {/* 천간 */}
                      <div className="mb-1">
                        <p className="text-2xl font-bold text-purple-700">{item.pillar.gan}</p>
                        <p className="text-xs text-purple-500">{item.pillar.gan_element}</p>
                      </div>
                      {/* 지지 */}
                      <div className="border-t border-amber-200 pt-1">
                        <p className="text-2xl font-bold text-amber-600">{item.pillar.ji}</p>
                        <p className="text-xs text-amber-500">{item.pillar.ji_element}</p>
                      </div>
                      {/* 시주면 시간 범위 표시 */}
                      {idx === 0 && item.pillar.ji_index !== undefined && (
                        <p className="text-[10px] text-gray-400 mt-1">
                          {getHourRange(item.pillar.ji_index)}
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="text-gray-400 py-4">-</p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* 일간 설명 */}
          <div className="bg-purple-50 rounded-xl p-4 border border-purple-100">
            <p className="text-sm text-purple-600 font-medium mb-1">
              당신의 일간 (나를 나타내는 글자)
            </p>
            <p className="text-lg font-bold text-purple-800">
              {calculateResult.day_master} ({calculateResult.day_master_element})
            </p>
            <p className="text-sm text-gray-600 mt-2">
              {calculateResult.day_master_description}
            </p>
          </div>

          {/* 경계일 경고 */}
          {calculateResult.is_boundary_date && calculateResult.boundary_warning && (
            <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800">
              {calculateResult.boundary_warning}
            </div>
          )}

          {/* 기준 고지 (항상 노출) */}
          <div className="mt-4 text-center">
            <p className="text-xs text-gray-400">
              기준: KST(Asia/Seoul) · 시주는 2시간 단위(범위 기준)로 계산됩니다.
            </p>
          </div>
        </div>
      </div>

      {/* 해석 결과 카드 */}
      <div className="bg-white rounded-2xl shadow-lg overflow-hidden result-card">
        {/* 탭 네비게이션 */}
        <div className="flex border-b">
          {[
            { key: 'summary', label: '📊 요약' },
            { key: 'detail', label: '🔍 상세분석' },
            { key: 'action', label: '✅ 행동지침' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as 'summary' | 'detail' | 'action')}
              className={`flex-1 py-4 text-sm font-medium transition ${
                activeTab === tab.key
                  ? 'text-purple-600 border-b-2 border-purple-600 bg-purple-50'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {/* 요약 탭 */}
          {activeTab === 'summary' && (
            <div className="space-y-6">
              {/* 한 줄 요약 */}
              <div className="text-center py-4">
                <p className="text-xl font-bold text-gray-800">{interpretResult.summary}</p>
              </div>

              {/* 강점 & 주의점 */}
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-green-50 rounded-xl p-4">
                  <h4 className="font-bold text-green-700 mb-3">💪 강점</h4>
                  <ul className="space-y-2">
                    {interpretResult.strengths.map((s, i) => (
                      <li key={i} className="text-sm text-gray-700 flex items-start">
                        <span className="text-green-500 mr-2">✓</span>
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="bg-orange-50 rounded-xl p-4">
                  <h4 className="font-bold text-orange-700 mb-3">⚡ 주의점</h4>
                  <ul className="space-y-2">
                    {interpretResult.risks.map((r, i) => (
                      <li key={i} className="text-sm text-gray-700 flex items-start">
                        <span className="text-orange-500 mr-2">!</span>
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* 행운 요소 */}
              {interpretResult.lucky_elements && (
                <div className="bg-amber-50 rounded-xl p-4">
                  <h4 className="font-bold text-amber-700 mb-3">🍀 행운 요소</h4>
                  <div className="flex flex-wrap gap-4">
                    {interpretResult.lucky_elements.color && (
                      <div className="text-center">
                        <p className="text-xs text-gray-500">행운의 색</p>
                        <p className="font-bold text-amber-800">{interpretResult.lucky_elements.color}</p>
                      </div>
                    )}
                    {interpretResult.lucky_elements.direction && (
                      <div className="text-center">
                        <p className="text-xs text-gray-500">행운의 방향</p>
                        <p className="font-bold text-amber-800">{interpretResult.lucky_elements.direction}</p>
                      </div>
                    )}
                    {interpretResult.lucky_elements.number && (
                      <div className="text-center">
                        <p className="text-xs text-gray-500">행운의 숫자</p>
                        <p className="font-bold text-amber-800">{interpretResult.lucky_elements.number}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 상세분석 탭 */}
          {activeTab === 'detail' && (
            <div className="space-y-6">
              <div>
                <h4 className="font-bold text-gray-800 mb-2">🧬 일간(나) 분석</h4>
                <p className="text-gray-700 leading-relaxed bg-gray-50 p-4 rounded-lg">
                  {interpretResult.day_master_analysis}
                </p>
              </div>

              <div>
                <h4 className="font-bold text-gray-800 mb-2">💬 질문에 대한 답변</h4>
                <p className="text-gray-700 leading-relaxed bg-purple-50 p-4 rounded-lg border-l-4 border-purple-400">
                  {interpretResult.answer}
                </p>
              </div>

              {interpretResult.lucky_periods.length > 0 && (
                <div>
                  <h4 className="font-bold text-gray-800 mb-2">📅 좋은 시기</h4>
                  <div className="flex flex-wrap gap-2">
                    {interpretResult.lucky_periods.map((period, i) => (
                      <span key={i} className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm">
                        {period}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {interpretResult.caution_periods.length > 0 && (
                <div>
                  <h4 className="font-bold text-gray-800 mb-2">⚠️ 조심할 시기</h4>
                  <div className="flex flex-wrap gap-2">
                    {interpretResult.caution_periods.map((period, i) => (
                      <span key={i} className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm">
                        {period}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 행동지침 탭 */}
          {activeTab === 'action' && (
            <div className="space-y-6">
              <div>
                <h4 className="font-bold text-gray-800 mb-4">📋 구체적 행동 조언</h4>
                <div className="space-y-3">
                  {interpretResult.action_plan.map((action, i) => (
                    <div key={i} className="flex items-start p-4 bg-blue-50 rounded-xl">
                      <span className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-bold mr-3">
                        {i + 1}
                      </span>
                      <p className="text-gray-700 pt-1">{action}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="text-center py-6 bg-gradient-to-r from-purple-50 to-amber-50 rounded-xl">
                <p className="text-xl text-purple-700 font-medium">
                  ✨ {interpretResult.blessing}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* 면책조항 */}
        <div className="px-6 pb-6">
          <div className="disclaimer">
            {interpretResult.disclaimer}
          </div>
        </div>
      </div>

      {/* 정확도 배지 (CTA 근처 재표시) */}
      <div className={`p-3 rounded-lg text-center ${
        accuracyBadge === 'high' ? 'bg-green-50' :
        accuracyBadge === 'boundary' ? 'bg-yellow-50' :
        'bg-blue-50'
      }`}>
        <p className={`text-sm ${
          accuracyBadge === 'high' ? 'text-green-600' :
          accuracyBadge === 'boundary' ? 'text-yellow-600' :
          'text-blue-600'
        }`}>
          {badgeInfo.icon} {badgeInfo.label}
        </p>
      </div>

      {/* 액션 버튼 */}
      <div className="flex gap-4">
        <button
          onClick={handleShare}
          className="flex-1 py-4 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white font-bold rounded-xl shadow-lg transition share-button"
        >
          📤 결과 공유하기
        </button>
        <button
          onClick={onReset}
          className="flex-1 py-4 bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold rounded-xl transition"
        >
          🔄 다시 하기
        </button>
      </div>

      {/* 메타 정보 */}
      <div className="text-center text-xs text-gray-400">
        <p>Model: {interpretResult.model_used} | Tokens: {interpretResult.tokens_used || 'N/A'}</p>
        <p>Method: {calculateResult.calculation_method}</p>
      </div>

      {/* 경계일 경고 모달 */}
      {showBoundaryModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full">
            <h3 className="text-lg font-bold text-yellow-700 mb-3">
              ⚠️ 절기 경계일 안내
            </h3>
            <p className="text-gray-600 mb-4">
              이 날짜는 절기 경계에 가깝습니다. 
              출생시간에 따라 월주/연주가 달라질 수 있어 결과에 오차가 있을 수 있습니다.
            </p>
            <p className="text-sm text-gray-500 mb-4">
              그래도 공유하시겠습니까?
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowBoundaryModal(false);
                  doShare();
                }}
                className="flex-1 py-3 bg-yellow-500 hover:bg-yellow-600 text-white font-bold rounded-lg"
              >
                공유하기
              </button>
              <button
                onClick={() => setShowBoundaryModal(false)}
                className="flex-1 py-3 bg-gray-200 hover:bg-gray-300 text-gray-700 font-bold rounded-lg"
              >
                취소
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
