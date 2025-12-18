'use client';

import { useState } from 'react';
import { 
  CONCERN_OPTIONS, 
  HOUR_OPTIONS,
  getHourFromJiIndex,
  type ConcernType 
} from '@/types';

interface SajuFormProps {
  onSubmit: (data: {
    name: string;
    birthYear: number;
    birthMonth: number;
    birthDay: number;
    birthHour: number | null;
    birthMinute: number;
    gender: 'male' | 'female' | 'other';
    concernType: ConcernType;
    question: string;
  }) => void;
}

export default function SajuForm({ onSubmit }: SajuFormProps) {
  const [name, setName] = useState('');
  const [birthYear, setBirthYear] = useState(1990);
  const [birthMonth, setBirthMonth] = useState(1);
  const [birthDay, setBirthDay] = useState(1);
  const [knowHour, setKnowHour] = useState(false);
  const [hourJiIndex, setHourJiIndex] = useState<number>(6); // 기본값: 오시
  const [gender, setGender] = useState<'male' | 'female' | 'other'>('female');
  const [concernType, setConcernType] = useState<ConcernType>('general');
  const [question, setQuestion] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // 시간대 인덱스 → 실제 시간 변환
    const birthHour = knowHour ? getHourFromJiIndex(hourJiIndex) : null;
    
    onSubmit({
      name: name || '고객님',
      birthYear,
      birthMonth,
      birthDay,
      birthHour,
      birthMinute: 0,
      gender,
      concernType,
      question: question || '올해 전반적인 운세가 궁금합니다.',
    });
  };

  const currentYear = new Date().getFullYear();

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg p-6 md:p-8 animate-fade-in-up">
      <h2 className="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
        <span>📝</span> 생년월일 입력
      </h2>

      {/* 이름 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          이름 (닉네임)
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="홍길동"
          className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition"
        />
      </div>

      {/* 생년월일 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          생년월일 (양력)
        </label>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <select
              value={birthYear}
              onChange={(e) => setBirthYear(Number(e.target.value))}
              className="w-full px-3 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              {Array.from({ length: 100 }, (_, i) => currentYear - i).map((year) => (
                <option key={year} value={year}>{year}년</option>
              ))}
            </select>
          </div>
          <div>
            <select
              value={birthMonth}
              onChange={(e) => setBirthMonth(Number(e.target.value))}
              className="w-full px-3 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((month) => (
                <option key={month} value={month}>{month}월</option>
              ))}
            </select>
          </div>
          <div>
            <select
              value={birthDay}
              onChange={(e) => setBirthDay(Number(e.target.value))}
              className="w-full px-3 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => (
                <option key={day} value={day}>{day}일</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 출생 시간 - 개선된 UI */}
      <div className="mb-6">
        <div className="flex items-center mb-3">
          <input
            type="checkbox"
            id="knowHour"
            checked={knowHour}
            onChange={(e) => setKnowHour(e.target.checked)}
            className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
          />
          <label htmlFor="knowHour" className="ml-2 text-sm font-medium text-gray-700">
            출생시간을 알고 있어요
          </label>
        </div>
        
        {knowHour && (
          <div className="space-y-3">
            {/* 시간대 선택 (2시간 단위) */}
            <select
              value={hourJiIndex}
              onChange={(e) => setHourJiIndex(Number(e.target.value))}
              className="w-full px-3 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-base"
            >
              {HOUR_OPTIONS.map((option) => (
                <option key={option.index} value={option.index}>
                  {option.ji_hanja}시 ({option.ji}시) - {option.range_start}~{option.range_end}
                </option>
              ))}
            </select>
            
            {/* 시간대 기준 안내 */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-sm text-blue-700">
                ℹ️ 시주는 2시간 단위(위 범위)로 계산됩니다. 경계 시간은 범위 기준을 따릅니다.
              </p>
              <p className="text-xs text-blue-600 mt-1">
                예: 10시 59분 = {HOUR_OPTIONS[5].ji_hanja}시({HOUR_OPTIONS[5].range_start}~{HOUR_OPTIONS[5].range_end}), 
                11시 00분 = {HOUR_OPTIONS[6].ji_hanja}시({HOUR_OPTIONS[6].range_start}~{HOUR_OPTIONS[6].range_end})
              </p>
            </div>
          </div>
        )}
        
        {!knowHour && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-sm text-amber-700">
              ⚠️ 시간 미입력시 시주(시기운) 분석이 생략됩니다.
            </p>
            <p className="text-xs text-amber-600 mt-1">
              정확한 분석을 위해 출생시간 입력을 권장합니다.
            </p>
          </div>
        )}
      </div>

      {/* 성별 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          성별
        </label>
        <div className="flex gap-3">
          {[
            { value: 'male', label: '남성', emoji: '👨' },
            { value: 'female', label: '여성', emoji: '👩' },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setGender(option.value as 'male' | 'female')}
              className={`flex-1 py-3 px-4 rounded-lg border-2 transition ${
                gender === option.value
                  ? 'border-purple-500 bg-purple-50 text-purple-700'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <span className="mr-2">{option.emoji}</span>
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* 고민 유형 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          고민 분야
        </label>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {CONCERN_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setConcernType(option.value)}
              className={`py-3 px-4 rounded-lg border-2 text-sm transition ${
                concernType === option.value
                  ? 'border-purple-500 bg-purple-50 text-purple-700'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <span className="mr-1">{option.emoji}</span>
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* 질문 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          구체적인 고민/질문
        </label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="예: 올해 결혼할 수 있을까요? / 이직을 고민하고 있는데 언제가 좋을까요?"
          rows={3}
          className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
        />
      </div>

      {/* 면책조항 (CTA 근처) */}
      <div className="mb-4 bg-gray-50 border border-gray-200 rounded-lg p-3">
        <p className="text-xs text-gray-500">
          ⚠️ 본 서비스는 <strong>오락/참고 목적</strong>으로 제공됩니다. 
          의학/법률/투자 등 전문적 조언을 대체하지 않습니다.
        </p>
      </div>

      {/* 제출 버튼 */}
      <button
        type="submit"
        className="w-full py-4 bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white font-bold text-lg rounded-xl shadow-lg hover:shadow-xl transition transform hover:-translate-y-0.5"
      >
        🔮 사주 분석하기
      </button>
    </form>
  );
}
