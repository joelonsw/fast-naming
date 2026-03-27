"""
Few-shot 예시 로더
web/examples/examples.json에서 예시 데이터를 로드
"""

import json
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

from contest_intelligence import rank_examples_for_contest

# examples.json 경로 (agent 디렉토리 기준)
EXAMPLES_PATH = os.path.join(os.path.dirname(__file__), "..", "web", "examples", "examples.json")


def load_examples() -> List[Dict[str, str]]:
    """examples.json에서 예시 데이터 로드"""
    
    try:
        if os.path.exists(EXAMPLES_PATH):
            with open(EXAMPLES_PATH, "r", encoding="utf-8") as f:
                examples = json.load(f)
                logger.info(f"✅ {len(examples)}개 예시 로드 완료")
                return examples
        else:
            logger.warning(f"⚠️ examples.json을 찾을 수 없습니다: {EXAMPLES_PATH}")
            return []
    except Exception as e:
        logger.error(f"❌ 예시 로드 실패: {e}")
        return []


def filter_examples(
    examples: List[Dict[str, str]],
    contest_type: Optional[str] = None,
    held_by_type: Optional[str] = None,
) -> List[Dict[str, str]]:
    """조건에 맞는 예시 필터링
    
    Args:
        examples: 전체 예시 목록
        contest_type: 공모전 유형 (네이밍, 슬로건 등)
        held_by_type: 기관 유형 (공공기관, 사기업, 학교)
        
    Returns:
        필터링된 예시 목록
    """
    
    if not examples:
        return []
    
    filtered = examples
    
    # 1차: contest_type과 held_by_type 모두 일치
    if contest_type and held_by_type:
        exact_match = [
            ex for ex in filtered
            if ex.get("contestType") == contest_type 
            and ex.get("contestHeldByType") == held_by_type
        ]
        if exact_match:
            logger.info(f"🎯 정확한 매칭: {len(exact_match)}개")
            return exact_match
    
    # 2차: contest_type만 일치
    if contest_type:
        type_match = [
            ex for ex in filtered
            if ex.get("contestType") == contest_type
        ]
        if type_match:
            logger.info(f"📋 유형 매칭: {len(type_match)}개")
            return type_match
    
    # 3차: 전체 반환
    logger.info(f"📚 전체 예시 사용: {len(filtered)}개")
    return filtered


def get_examples_for_contest(
    contest_type: str,
    held_by_type: str,
    contest_title: str = "",
    contest_content: str = "",
    held_by: str = "",
) -> List[Dict[str, str]]:
    """공모전에 맞는 예시 가져오기"""
    
    examples = load_examples()
    filtered = filter_examples(examples, contest_type, held_by_type)

    if contest_title or contest_content or held_by:
        ranked = rank_examples_for_contest(
            filtered,
            {
                "title": contest_title,
                "content": contest_content,
                "held_by": held_by,
                "contest_type": contest_type,
                "held_by_type": held_by_type,
                "url": "",
                "submission_method": "",
                "deadline": None,
                "d_day": None,
            },
        )
        logger.info("🎯 공모전 문맥 기준 예시 재정렬 완료")
        return ranked

    return filtered


# 테스트용
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    all_examples = load_examples()
    print(f"전체 예시: {len(all_examples)}개")
    
    # 공공기관 슬로건 예시
    slogan_examples = filter_examples(all_examples, "슬로건", "공공기관")
    print(f"공공기관 슬로건 예시: {len(slogan_examples)}개")
    
    for ex in slogan_examples[:3]:
        print(f"  - {ex.get('contestTitle')}: {ex.get('contestWinner')}")
