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
from llm_clients import get_configured_provider_names
from contest_intelligence import build_contest_profile

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
        if not os.getenv("SLACK_WEBHOOK"):
            raise ValueError("필수 환경변수 누락: ['SLACK_WEBHOOK']")

        configured_providers = get_configured_provider_names()
        if not configured_providers:
            raise ValueError(
                "사용 가능한 LLM API 키가 없습니다. "
                "HUGGINGFACE_API_KEY(HF_TOKEN), GROQ_API_KEY, GEMINI_API_KEY, AI_GITHUB_TOKEN 중 하나 이상이 필요합니다."
            )
        
        logger.info("🚀 Fast-Naming AI Agent 초기화 완료")
        logger.info("🤖 사용 가능한 LLM 제공자: %s", ", ".join(configured_providers))
    
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
            "contest_profile": {},
            "phase_models": {},
        }
        
        # === Phase 1: 초기 생성 ===
        logger.info("   📚 Few-shot 예시 로드...")
        contest_profile = build_contest_profile(contest)
        result["contest_profile"] = {
            "keywords": contest_profile.get("keywords", []),
            "domain_tags": contest_profile.get("domain_tags", []),
            "preferred_traits": contest_profile.get("preferred_traits", []),
            "organizer_profile": contest_profile.get("organizer_profile", {}),
        }
        logger.info(
            "   🧭 공모전 프로필 | 키워드=%s | 분야=%s",
            ", ".join(contest_profile.get("keywords", [])[:6]) or "없음",
            ", ".join(contest_profile.get("domain_tags", [])) or "일반",
        )
        examples = get_examples_for_contest(
            contest["contest_type"],
            contest["held_by_type"],
            contest_title=contest["title"],
            contest_content=contest["content"],
            held_by=contest["held_by"],
        )
        logger.info(f"   → {len(examples)}개 예시 로드됨")
        if examples:
            logger.info(
                "   📚 참고 수상작 예시: %s",
                " | ".join(ex.get("contestTitle", "") for ex in examples[:3]),
            )
        
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
            {
                "name": s["name"],
                "score": s.get("score", 0),
                "provider": s.get("provider", ""),
                "model": s.get("model", ""),
                "strategy": s.get("strategy", ""),
            }
            for s in top3
        ]
        
        logger.info("   🏆 최종 TOP 3:")
        for i, sub in enumerate(top3, 1):
            score = sub.get("score", 0) or 0
            logger.info(
                f"      {i}. {sub['name']} (점수: {score:.1f}, 모델: {sub.get('provider', '')}/{sub.get('model', '')}, 전략: {sub.get('strategy', '')})"
            )

        phase_models = {
            "top3": [
                f"{sub.get('provider', '')}/{sub.get('model', '')}"
                for sub in top3
            ],
        }
        result["phase_models"] = phase_models
        
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


async def run_single_contest(contest_url: str = None, contest_data: str = None):
    """단일 공모전 처리 (병렬 실행용)
    
    Args:
        contest_url: 공모전 URL (스크래핑 필요)
        contest_data: JSON 형태의 공모전 데이터 (스크래핑 불필요)
    """
    from scraper import scrape_contest_detail
    
    logger.info("=" * 60)
    logger.info("🎯 단일 공모전 처리 모드")
    logger.info("=" * 60)
    
    state = create_initial_state()
    
    # 공모전 정보 획득
    if contest_data:
        # JSON 데이터로 직접 전달받은 경우
        contest = json.loads(contest_data)
        logger.info(f"📌 공모전: {contest.get('title', contest_url)}")
    elif contest_url:
        # URL만 있는 경우 상세 스크래핑
        logger.info(f"🔍 공모전 URL: {contest_url}")
        contest = await scrape_contest_detail(contest_url)
        if not contest:
            logger.error("❌ 공모전 정보를 가져올 수 없습니다")
            return None
        logger.info(f"📌 공모전: {contest['title']}")
    else:
        logger.error("❌ contest_url 또는 contest_data가 필요합니다")
        return None
    
    agent = NamingAgent()
    result = await agent.process_single_contest(contest, state)
    
    # 결과 저장
    os.makedirs("results", exist_ok=True)
    safe_title = "".join(c for c in contest.get('title', 'unknown')[:30] if c.isalnum() or c in ' -_').strip()
    result_file = f"results/{safe_title}_{datetime.now().strftime('%H%M%S')}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    
    logger.info(f"📁 결과 저장: {result_file}")
    return result


async def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fast-Naming AI Agent")
    parser.add_argument("--contest-url", type=str, help="단일 공모전 URL (병렬 처리용)")
    parser.add_argument("--contest-data", type=str, help="단일 공모전 JSON 데이터")
    parser.add_argument("--mode", type=str, choices=["all", "single"], default="all",
                        help="실행 모드: all(전체), single(단일)")
    args = parser.parse_args()
    
    # 단일 공모전 처리 모드
    if args.contest_url or args.contest_data:
        return await run_single_contest(
            contest_url=args.contest_url,
            contest_data=args.contest_data,
        )
    
    # 전체 처리 모드 (기존 방식)
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
