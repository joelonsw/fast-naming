"""
Contest Processor for handling contest data analysis and submission generation.
This module manages the entire workflow from contest input to result generation.
"""

import json
import os
import random
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from async_llm_client import create_async_llm_orchestrator

logger = logging.getLogger(__name__)


class AsyncContestProcessor:
    """Main processor for contest submission generation."""
    
    def __init__(self):
        logger.info("🔧 ContestProcessor 초기화 시작")
        self.examples_data = self._load_examples()
        logger.info(f"📚 예시 데이터 로드 완료: {len(self.examples_data)}개")
        self.llm_orchestrator = create_async_llm_orchestrator()
        logger.info("🤖 LLM Orchestrator 생성 완료")
        self.result_counter = self._get_next_result_number()
        logger.info(f"📁 다음 결과 파일 번호: {self.result_counter}")
        logger.info("✅ ContestProcessor 초기화 완료")
    
    def _load_examples(self) -> List[Dict[str, str]]:
        """Load examples from examples.json file."""
        logger.info("📖 examples.json 파일 로드 시작")
        try:
            with open("examples/examples.json", "r", encoding="utf-8") as f:
                examples = json.load(f)
                logger.info(f"✅ examples.json 로드 성공: {len(examples)}개 예시")
                return examples
        except FileNotFoundError:
            logger.warning("⚠️ examples/examples.json 파일을 찾을 수 없습니다. 빈 예시를 사용합니다.")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"❌ examples.json 파싱 오류: {e}")
            return []
    
    def _get_next_result_number(self) -> int:
        """Get the next result file number."""
        if not os.path.exists("result"):
            os.makedirs("result")
            return 1
        
        existing_files = [f for f in os.listdir("result") if f.startswith("result") and f.endswith(".json")]
        if not existing_files:
            return 1
        
        numbers = []
        for file in existing_files:
            try:
                number = int(file.replace("result", "").replace(".json", ""))
                numbers.append(number)
            except ValueError:
                continue
        
        return max(numbers) + 1 if numbers else 1
    
    def extract_successful_examples(self, contest_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract successful examples based on contest type and held by type."""
        contest_type = contest_data.get("contestType")
        contest_held_by_type = contest_data.get("contestHeldByType")
        
        logger.info(f"🔍 예시 추출 시작: contestType={contest_type}, contestHeldByType={contest_held_by_type}")
        
        if not contest_type or not contest_held_by_type:
            logger.warning("⚠️ contestType 또는 contestHeldByType이 없습니다.")
            return []
        
        # Filter examples by contest type and held by type
        matching_examples = [
            example for example in self.examples_data
            if example.get("contestType") == contest_type and 
               example.get("contestHeldByType") == contest_held_by_type
        ]
        
        logger.info(f"🎯 정확한 매칭 예시: {len(matching_examples)}개")
        
        # If no exact matches, try to find similar examples
        if not matching_examples:
            logger.info("🔍 정확한 매칭이 없어 contestType만으로 검색합니다.")
            # Try matching just contest type
            matching_examples = [
                example for example in self.examples_data
                if example.get("contestType") == contest_type
            ]
            logger.info(f"🎯 contestType 매칭 예시: {len(matching_examples)}개")
        
        if not matching_examples:
            logger.info("🔍 매칭되는 예시가 없어 모든 예시를 사용합니다.")
            # If still no matches, return all examples
            matching_examples = self.examples_data
        
        logger.info(f"✅ 최종 선택된 예시: {len(matching_examples)}개")
        for i, example in enumerate(matching_examples[:3], 1):
            logger.info(f"   예시 {i}: {example.get('contestTitle', 'N/A')} -> {example.get('contestWinner', 'N/A')}")
        
        return matching_examples
    
    async def generate_submissions(self, contest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate contest submissions using LLM orchestrator."""
        logger.info("🎯 작명 생성 프로세스 시작")
        
        try:
            # Extract successful examples
            logger.info("📚 1단계: 성공 예시 추출")
            successful_examples = self.extract_successful_examples(contest_data)
            
            if not successful_examples:
                logger.error("❌ 매칭되는 예시를 찾을 수 없습니다.")
                return {
                    "error": "No matching examples found for the contest type and held by type."
                }
            
            # Generate submissions using LLM orchestrator
            logger.info("🤖 2단계: LLM을 통한 작명 생성 시작")
            submissions = await self.llm_orchestrator.generate_submissions(
                contest_data=contest_data,
                successful_examples=successful_examples,
                num_iterations=5
            )
            logger.info(f"✅ LLM 작명 생성 완료: {len(submissions)}개 생성됨")
            
            # Create result structure
            logger.info("📊 3단계: 결과 구조 생성")
            result = {
                "contest_data": contest_data,
                "successful_examples_used": successful_examples,
                "submissions": submissions,
                "generated_at": datetime.now().isoformat(),
                "total_submissions": len(submissions)
            }
            
            # Save result to file
            logger.info("💾 4단계: 결과 파일 저장")
            self._save_result(result)
            
            logger.info("🎉 작명 생성 프로세스 완료!")
            return result
            
        except Exception as e:
            logger.error(f"❌ 작명 생성 중 오류 발생: {str(e)}", exc_info=True)
            return {
                "error": f"Failed to generate submissions: {str(e)}"
            }
    
    def _save_result(self, result: Dict[str, Any]):
        """Save result to JSON file."""
        filename = f"result/result{self.result_counter:04d}.json"
        
        logger.info(f"💾 결과 파일 저장 시작: {filename}")
        
        try:
            # result 디렉토리가 없으면 생성
            os.makedirs("result", exist_ok=True)
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 결과 파일 저장 완료: {filename}")
            self.result_counter += 1
            
        except Exception as e:
            logger.error(f"❌ 결과 파일 저장 실패: {e}")
            raise
    
    def get_statistics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate statistics from the result."""
        if "error" in result:
            return {"error": result["error"]}
        
        submissions = result.get("submissions", [])
        
        # Count by provider
        provider_counts = {}
        model_counts = {}
        temperature_stats = []
        top_p_stats = []
        
        for submission in submissions:
            provider = submission.get("provider", "unknown")
            model = submission.get("model", "unknown")
            temperature = submission.get("temperature", 0)
            top_p = submission.get("top_p", 0)
            
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            model_counts[model] = model_counts.get(model, 0) + 1
            temperature_stats.append(temperature)
            top_p_stats.append(top_p)
        
        return {
            "total_submissions": len(submissions),
            "provider_distribution": provider_counts,
            "model_distribution": model_counts,
            "temperature_range": {
                "min": min(temperature_stats) if temperature_stats else 0,
                "max": max(temperature_stats) if temperature_stats else 0,
                "avg": sum(temperature_stats) / len(temperature_stats) if temperature_stats else 0
            },
            "top_p_range": {
                "min": min(top_p_stats) if top_p_stats else 0,
                "max": max(top_p_stats) if top_p_stats else 0,
                "avg": sum(top_p_stats) / len(top_p_stats) if top_p_stats else 0
            }
        }


# Convenience function
def create_async_contest_processor() -> AsyncContestProcessor:
    """Create and return a contest processor instance."""
    return AsyncContestProcessor()
