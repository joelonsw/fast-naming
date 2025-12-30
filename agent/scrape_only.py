"""
Fast-Naming Scraper Only
공모전 목록만 스크래핑하여 JSON 출력 (GitHub Actions Matrix용)
"""

import os
import sys
import json
import asyncio
import logging
from typing import List, Dict

from dotenv import load_dotenv

from scraper import scrape_all_contests
from notion_saver import get_processed_urls

# 환경변수 로드
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=env_path)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]  # stderr로 로그 출력
)
logger = logging.getLogger(__name__)


async def scrape_contests_only() -> List[Dict]:
    """공모전 목록만 스크래핑"""
    
    logger.info("🔍 공모전 스크래핑 시작...")
    
    # 이미 처리된 URL 조회
    try:
        processed_urls = await get_processed_urls()
        logger.info(f"📋 기존 처리된 공모전: {len(processed_urls)}개")
    except Exception as e:
        logger.warning(f"Notion 조회 실패: {e}")
        processed_urls = []
    
    # 공모전 스크래핑
    contests = await scrape_all_contests(exclude_urls=processed_urls)
    logger.info(f"✅ 새 공모전 발견: {len(contests)}개")
    
    # 필요한 정보만 추출
    result = []
    for contest in contests:
        result.append({
            "url": contest.get("url", ""),
            "title": contest.get("title", ""),
            "contest_type": contest.get("contest_type", ""),
            "held_by_type": contest.get("held_by_type", ""),
            "deadline": contest.get("deadline", ""),
            "d_day": contest.get("d_day", ""),
        })
    
    return result


async def main():
    """메인 실행"""
    contests = await scrape_contests_only()
    
    # JSON 출력 (stdout으로 - GitHub Actions에서 파싱)
    print(json.dumps(contests, ensure_ascii=False, indent=2))
    
    # 결과 파일 저장 (백업용)
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)
    
    output_path = os.path.join(results_dir, "contests.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(contests, f, ensure_ascii=False, indent=2)
    
    logger.info(f"📁 결과 저장: {output_path}")
    
    return contests


if __name__ == "__main__":
    asyncio.run(main())
