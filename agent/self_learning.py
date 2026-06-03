"""
재귀적 자기 학습 엔진 (Self-Learning Engine)
LLM이 스스로 생성한 결과를 분석하고, 다음 생성에 반영하는 피드백 루프
"""

import json
import asyncio
import logging
from typing import List, Dict, Any
from collections import Counter

from state import ContestInfo, Submission
from contest_intelligence import build_contest_profile
from llm_clients import create_primary_client, get_rate_limit_delay

logger = logging.getLogger(__name__)


class SelfLearningEngine:
    """
    재귀적 자기 학습 시스템
    
    1. 생성된 작명들의 패턴 분석
    2. 높은 점수를 받은 작명의 특징 추출
    3. 다음 생성 시 해당 특징 강화
    4. 반복을 통한 품질 향상
    """
    
    def __init__(self):
        self.client = create_primary_client(temperature=0.7, max_tokens=2048)
        if self.client:
            logger.info("🧠 Self-Learning 모델: %s/%s", self.client.provider_name, self.client.model_name)
        
        # 학습된 패턴 저장
        self.learned_patterns: Dict[str, Any] = {
            "successful_keywords": [],
            "effective_strategies": [],
            "style_preferences": {},
            "improvement_history": [],
        }
    
    async def analyze_successful_patterns(
        self, 
        submissions: List[Submission],
        top_threshold: float = 0.7,  # 상위 70% 이상을 "성공"으로 간주
    ) -> Dict[str, Any]:
        """성공적인 작명들의 패턴 분석"""
        
        if not submissions:
            return {}
        
        # 점수순 정렬
        scored = [s for s in submissions if s.get('score') is not None]
        if not scored or not self.client:
            return {}
        
        scored.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # 상위 작명 선택
        cutoff = max(1, int(len(scored) * (1 - top_threshold)))
        top_submissions = scored[:cutoff]
        
        # 패턴 분석을 LLM에게 요청
        top_text = "\n".join([
            f"- {s['name']} (점수: {s.get('score', 0):.1f}, 전략: {s.get('strategy', 'Unknown')})"
            for s in top_submissions[:10]
        ])
        
        system_prompt = """당신은 네이밍 패턴 분석가입니다.
높은 점수를 받은 작명의 공통 패턴만 간결하게 추출하세요."""

        prompt = f"""다음은 공모전에서 높은 점수를 받은 작명들입니다:

{top_text}

이 작명들의 공통 패턴을 분석해주세요:

1. 자주 사용된 키워드나 단어
2. 문장/어구 구조 (길이, 형식)
3. 특히 효과적이었던 표현 기법
4. 공통적인 톤앤매너

반드시 다음 JSON 형식으로 응답하세요:
```json
{{
    "common_keywords": ["키워드1", "키워드2", ...],
    "effective_structures": ["구조1", "구조2", ...],
    "winning_techniques": ["기법1", "기법2", ...],
    "tone_and_manner": "분석된 톤앤매너 설명",
    "length_preference": "선호되는 길이 (짧음/중간/김)"
}}
```"""
        
        response = ""
        try:
            response = await self.client.generate(system_prompt, prompt)
            
            # <think> 태그 제거
            import re
            cleaned_response = re.sub(r'<think>[\s\S]*?</think>', '', response).strip()
            
            # JSON 블록 추출
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', cleaned_response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 백틱이 없는 경우 가장 바깥쪽 중괄호 검색
                brace_match = re.search(r'\{[\s\S]*\}', cleaned_response)
                json_str = brace_match.group(0) if brace_match else cleaned_response
            
            analysis = json.loads(json_str.strip())
            
            # 학습 결과 저장
            common_kws = analysis.get("common_keywords", [])
            effective_strats = analysis.get("winning_techniques", [])
            
            self.learned_patterns["successful_keywords"].extend(common_kws)
            self.learned_patterns["effective_strategies"].extend(effective_strats)
            
            logger.info(f"✅ 패턴 분석 완료: {len(common_kws)}개 키워드 발견")
            
            await asyncio.sleep(get_rate_limit_delay(self.client.provider_name))
            return analysis
            
        except Exception as e:
            logger.error(f"❌ 패턴 분석 실패: {e} | 응답 원본 일부: {response[:150]}...")
            return {}
    
    async def generate_improved_prompt(
        self,
        contest: ContestInfo,
        analysis: Dict[str, Any],
        iteration: int,
    ) -> str:
        """분석 결과를 바탕으로 개선된 프롬프트 생성"""
        
        base_prompt = f"""{contest['title']} 공모전에 참여하여 1등을 수상할 작명 3개를 만드세요.

<공모전 내용>
{contest['content'][:1500]}
</공모전 내용>

"""
        base_prompt += build_contest_profile(contest).get("prompt_boost", "") + "\n"
        
        # 학습된 패턴 주입
        if analysis:
            base_prompt += f"""
<성공 패턴 분석 결과 - {iteration}차 학습>
이전 생성에서 높은 점수를 받은 작명들의 공통 특징입니다. 
이 특징들을 새로운 작명에 적극 반영하세요:

- 효과적인 키워드: {', '.join(analysis.get('common_keywords', [])[:5])}
- 성공적인 기법: {', '.join(analysis.get('winning_techniques', [])[:3])}
- 선호되는 스타일: {analysis.get('tone_and_manner', '자연스럽고 기억에 남는')}
- 적절한 길이: {analysis.get('length_preference', '간결함')}
</성공 패턴 분석 결과>

"""
        
        base_prompt += """
반드시 다음 JSON 형식으로만 응답하세요:
```json
[
    {"submission": "작명1", "description": "작명 이유"},
    {"submission": "작명2", "description": "작명 이유"},
    {"submission": "작명3", "description": "작명 이유"}
]
```"""
        
        return base_prompt
    
    async def recursive_improvement_cycle(
        self,
        contest: ContestInfo,
        initial_submissions: List[Submission],
        evaluate_fn,  # 평가 함수
        criteria: Dict[str, int],
        max_iterations: int = 3,
        target_score: float = 90.0,
    ) -> List[Submission]:
        """재귀적 개선 사이클
        
        Args:
            contest: 공모전 정보
            initial_submissions: 초기 생성된 작명들
            evaluate_fn: 평가 함수
            criteria: 평가 기준
            max_iterations: 최대 반복 횟수
            target_score: 목표 점수
            
        Returns:
            개선된 작명 목록
        """
        
        logger.info(f"🔄 재귀적 개선 사이클 시작 (최대 {max_iterations}회)")
        
        all_submissions = initial_submissions.copy()
        best_score = max((s.get('score', 0) or 0) for s in all_submissions) if all_submissions else 0
        
        for iteration in range(1, max_iterations + 1):
            logger.info(f"\n🔁 반복 {iteration}/{max_iterations} (현재 최고점: {best_score:.1f})")
            
            # 목표 점수 도달 시 조기 종료 (최소 1회는 무조건 실행하도록 보장)
            if iteration > 1 and best_score >= target_score:
                logger.info(f"🎯 목표 점수 {target_score} 달성! 조기 종료")
                break
            
            # 1. 현재까지의 성공 패턴 분석
            analysis = await self.analyze_successful_patterns(all_submissions)
            
            if not analysis:
                logger.warning("패턴 분석 실패, 기본 프롬프트 사용")
                continue
            
            # 2. 개선된 프롬프트 생성
            improved_prompt = await self.generate_improved_prompt(
                contest, analysis, iteration
            )
            
            # 3. 새로운 작명 생성
            new_submissions = await self._generate_with_improved_prompt(
                contest, improved_prompt, iteration
            )
            
            if not new_submissions:
                continue
            
            # 4. 새 작명 평가
            evaluated = await evaluate_fn(contest, new_submissions, criteria)
            
            # 5. 전체 목록에 추가
            all_submissions.extend(evaluated)
            
            # 6. 최고 점수 업데이트
            current_best = max((s.get('score', 0) or 0) for s in evaluated) if evaluated else 0
            if current_best > best_score:
                improvement = current_best - best_score
                best_score = current_best
                logger.info(f"📈 점수 개선: +{improvement:.1f} (새 최고점: {best_score:.1f})")
                
                # 개선 히스토리 기록
                self.learned_patterns["improvement_history"].append({
                    "iteration": iteration,
                    "improvement": improvement,
                    "analysis_used": analysis,
                })
            else:
                logger.info(f"📊 점수 유지 (최고점: {best_score:.1f})")
        
        logger.info(f"✅ 재귀적 개선 완료: 총 {len(all_submissions)}개 작명")
        return all_submissions
    
    async def _generate_with_improved_prompt(
        self,
        contest: ContestInfo,
        prompt: str,
        iteration: int,
    ) -> List[Submission]:
        """개선된 프롬프트로 작명 생성"""
        if not self.client:
            logger.error("❌ 자기 학습용 LLM이 없습니다")
            return []
        
        system_prompt = f"""당신은 대한민국 최고의 네이미스트입니다.
당신은 {iteration}차 학습을 통해 더욱 발전한 상태입니다.
이전 반복에서 배운 것을 적극 활용하세요.
{build_contest_profile(contest).get("prompt_boost", "")}"""
        
        try:
            response = await self.client.generate(system_prompt, prompt)
            
            # JSON 파싱
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                items = json.loads(json_match.group(1))
            else:
                items = json.loads(response.strip())
            
            submissions = []
            for item in items:
                sub = Submission(
                    name=item.get('submission', ''),
                    description=f"[{iteration}차 학습] {item.get('description', '')}",
                    strategy=f"Self-Learning-Iter{iteration}",
                    provider=self.client.provider_name,
                    model=self.client.model_name,
                    score=None,
                    criteria_scores=None,
                )
                submissions.append(sub)
            
            logger.info(f"✅ {iteration}차 학습으로 {len(submissions)}개 작명 생성")
            
            await asyncio.sleep(get_rate_limit_delay(self.client.provider_name))
            
            return submissions
            
        except Exception as e:
            logger.error(f"❌ 개선 프롬프트 생성 실패: {e}")
            return []
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """학습 결과 요약"""
        
        # 가장 효과적인 키워드 추출
        keyword_counts = Counter(self.learned_patterns["successful_keywords"])
        top_keywords = keyword_counts.most_common(10)
        
        return {
            "top_keywords": [k for k, _ in top_keywords],
            "total_iterations": len(self.learned_patterns["improvement_history"]),
            "total_improvement": sum(
                h.get("improvement", 0) 
                for h in self.learned_patterns["improvement_history"]
            ),
        }


# 테스트용
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        engine = SelfLearningEngine()
        
        # 테스트 데이터
        test_submissions = [
            Submission(
                name="디지털 나래", description="테스트", strategy="A",
                provider="test", model="test", score=85, criteria_scores={}
            ),
            Submission(
                name="스마트 비전", description="테스트", strategy="B",
                provider="test", model="test", score=78, criteria_scores={}
            ),
        ]
        
        analysis = await engine.analyze_successful_patterns(test_submissions)
        print(f"분석 결과: {json.dumps(analysis, ensure_ascii=False, indent=2)}")
    
    asyncio.run(main())
