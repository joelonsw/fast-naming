"""
Fast-Naming LangGraph AI Agent
메인 워크플로우 정의 및 실행
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List

from dotenv import load_dotenv

# 모듈 임포트
from state import NamingAgentState, ContestInfo, Submission, create_initial_state
from scraper import scrape_all_contests
from examples_loader import get_examples_for_contest
from llm_generator import generate_submissions, CREATIVE_STRATEGIES
from evaluator import generate_evaluation_criteria, evaluate_submissions, rank_submissions, get_top_n
from slack_notifier import send_slack_notification
from notion_saver import save_to_notion, get_processed_urls

# 환경변수 로드 (agent 디렉토리 기준으로 루트의 .env 찾기)
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=env_path)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


class NamingAgent:
    """Fast-Naming AI Agent"""
    
    def __init__(self):
        """Agent 초기화"""
        # 필수 환경변수 확인
        required_vars = ["GEMINI_API_KEY", "GROQ_API_KEY", "SLACK_WEBHOOK"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"필수 환경변수 누락: {missing}")
        
        logger.info("🚀 Fast-Naming AI Agent 초기화 완료")
    
    async def run(self) -> Dict[str, Any]:
        """Agent 실행"""
        
        logger.info("=" * 60)
        logger.info("🎯 Fast-Naming AI Agent 실행 시작")
        logger.info("=" * 60)
        
        state = create_initial_state()
        results = {
            "execution_date": state["execution_date"],
            "week_info": state["week_info"],
            "processed_contests": [],
            "errors": [],
        }
        
        try:
            # 1. 이미 처리된 공모전 URL 조회 (중복 방지)
            logger.info("\n📋 Step 1: 기존 처리된 공모전 조회")
            processed_urls = await get_processed_urls()
            state["processed_contest_urls"] = processed_urls
            logger.info(f"   → 기존 처리: {len(processed_urls)}개")
            
            # 2. 접수중인 공모전 스크래핑
            logger.info("\n🔍 Step 2: Wevity 공모전 스크래핑")
            contests = await scrape_all_contests(exclude_urls=processed_urls)
            state["contests"] = contests
            logger.info(f"   → 새 공모전: {len(contests)}개")
            
            if not contests:
                logger.info("✅ 새로운 공모전이 없습니다. 종료합니다.")
                return results
            
            # 3. 각 공모전 처리
            for idx, contest in enumerate(contests):
                logger.info(f"\n{'='*60}")
                logger.info(f"📌 공모전 {idx+1}/{len(contests)}: {contest['title']}")
                logger.info(f"{'='*60}")
                
                try:
                    contest_result = await self.process_single_contest(contest, state)
                    results["processed_contests"].append(contest_result)
                    
                except Exception as e:
                    error_msg = f"공모전 처리 실패 ({contest['title']}): {e}"
                    logger.error(f"❌ {error_msg}")
                    results["errors"].append(error_msg)
            
            logger.info("\n" + "=" * 60)
            logger.info("🎉 Fast-Naming AI Agent 실행 완료!")
            logger.info(f"   처리된 공모전: {len(results['processed_contests'])}개")
            logger.info(f"   오류: {len(results['errors'])}개")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Agent 실행 중 오류: {e}")
            results["errors"].append(str(e))
        
        return results
    
    async def process_single_contest(
        self, 
        contest: ContestInfo, 
        state: NamingAgentState
    ) -> Dict[str, Any]:
        """단일 공모전 처리 - 1등 달성을 위한 강화된 파이프라인"""
        
        result = {
            "contest_title": contest["title"],
            "contest_url": contest["url"],
            "submissions_count": 0,
            "top3": [],
            "slack_sent": False,
            "notion_saved": False,
        }
        
        # === Phase 1: 초기 생성 ===
        logger.info("   📚 Few-shot 예시 로드...")
        examples = get_examples_for_contest(
            contest["contest_type"],
            contest["held_by_type"]
        )
        logger.info(f"   → {len(examples)}개 예시 로드됨")
        
        logger.info("   🤖 작명 생성 중 (12가지 전략 × 3 LLM)...")
        submissions = await generate_submissions(
            contest=contest,
            examples=examples,
            strategies=CREATIVE_STRATEGIES,
        )
        result["submissions_count"] = len(submissions)
        logger.info(f"   → {len(submissions)}개 작명 생성됨")
        
        if not submissions:
            logger.warning("   ⚠️ 작명이 생성되지 않았습니다")
            return result
        
        # === Phase 2: 평가 기준 생성 및 Multi-Agent 평가 ===
        logger.info("   📊 평가 기준 생성...")
        criteria = await generate_evaluation_criteria(contest)
        logger.info(f"   → 평가 기준: {criteria}")
        
        logger.info("   🎯 Multi-Agent 평가 중 (3 LLM 교차 평가)...")
        evaluated = await evaluate_submissions(contest, submissions, criteria, use_multi_agent=True)
        
        # === Phase 3: 재귀적 자기 학습 ===
        from self_learning import SelfLearningEngine
        from refiner import (
            remove_duplicates, 
            ensure_strategy_diversity, 
            refine_top_submissions,
            tournament_selection,
            final_polish,
        )
        
        logger.info("   🔄 재귀적 자기 학습 시작...")
        learning_engine = SelfLearningEngine()
        all_submissions = await learning_engine.recursive_improvement_cycle(
            contest=contest,
            initial_submissions=evaluated,
            evaluate_fn=evaluate_submissions,
            criteria=criteria,
            max_iterations=2,  # 최대 2회 반복 (rate limit 고려)
            target_score=92.0,
        )
        
        learning_summary = learning_engine.get_learning_summary()
        logger.info(f"   → 학습 완료: 총 {learning_summary['total_iterations']}회 반복")
        
        # === Phase 4: 품질 향상 ===
        logger.info("   🧹 중복 제거...")
        unique_submissions = remove_duplicates(all_submissions, similarity_threshold=0.6)
        logger.info(f"   → {len(all_submissions)} → {len(unique_submissions)}개")
        
        ranked = rank_submissions(unique_submissions)
        
        logger.info("   🎯 전략 다양성 보장...")
        top10 = ensure_strategy_diversity(ranked, top_n=10)
        
        logger.info("   ✨ TOP 10 정제 중...")
        refined = await refine_top_submissions(contest, top10, None)
        
        if refined:
            logger.info("   🎯 정제된 작명 평가 중...")
            refined_evaluated = await evaluate_submissions(contest, refined, criteria, use_multi_agent=False)
            top10.extend(refined_evaluated)
            ranked_with_refined = rank_submissions(top10)
        else:
            ranked_with_refined = top10
        
        # === Phase 5: Tournament 선별 ===
        logger.info("   🏆 토너먼트 선별...")
        finalists = await tournament_selection(contest, ranked_with_refined, final_count=5)
        
        # === Phase 6: 최종 폴리싱 ===
        logger.info("   💎 최종 폴리싱...")
        polished = await final_polish(contest, finalists)
        
        # 최종 TOP 3 선정
        top3 = get_top_n(polished, 3)
        result["top3"] = [
            {"name": s["name"], "score": s.get("score", 0)}
            for s in top3
        ]
        
        logger.info("   🏆 최종 TOP 3:")
        for i, sub in enumerate(top3, 1):
            score = sub.get("score", 0) or 0
            logger.info(f"      {i}. {sub['name']} (점수: {score:.1f})")
        
        # === Phase 7: 저장 및 알림 ===
        notion_url = None
        if os.getenv("NOTION_API_KEY") and os.getenv("NOTION_PARENT_PAGE_ID"):
            logger.info("   📝 Notion 저장...")
            notion_url = await save_to_notion(contest, top3, state["week_info"], polished)
            result["notion_saved"] = notion_url is not None
        else:
            logger.info("   ⚠️ Notion 설정 없음")
        
        logger.info("   📤 Slack 알림 전송...")
        slack_sent = await send_slack_notification(contest, top3, notion_url)
        result["slack_sent"] = slack_sent
        
        return result


async def main():
    """메인 함수"""
    agent = NamingAgent()
    results = await agent.run()
    
    # 결과 저장 (로컬)
    os.makedirs("results", exist_ok=True)
    result_file = f"results/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    logger.info(f"📁 결과 저장: {result_file}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
