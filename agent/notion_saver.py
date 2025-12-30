"""
Notion 저장 모듈
결과를 Notion 페이지에 구조화하여 저장
"""

import os
import logging
from typing import List, Optional
from datetime import datetime

from notion_client import AsyncClient

from state import ContestInfo, Submission

logger = logging.getLogger(__name__)


class NotionSaver:
    """Notion 저장 관리자"""
    
    def __init__(self):
        self.api_key = os.getenv("NOTION_API_KEY")
        self.parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
        
        if not self.api_key:
            raise ValueError("NOTION_API_KEY 환경변수가 설정되지 않았습니다")
        if not self.parent_page_id:
            raise ValueError("NOTION_PARENT_PAGE_ID 환경변수가 설정되지 않았습니다")
        
        self.client = AsyncClient(auth=self.api_key)
    
    async def find_or_create_week_page(self, week_info: str) -> str:
        """주차 페이지 찾기 또는 생성
        
        Args:
            week_info: "2024년-12월-3주차" 형식의 주차 정보
            
        Returns:
            페이지 ID
        """
        logger.info(f"📁 주차 페이지 검색: {week_info}")
        
        # 기존 페이지 검색
        try:
            children = await self.client.blocks.children.list(
                block_id=self.parent_page_id
            )
            
            for block in children.get("results", []):
                if block["type"] == "child_page":
                    title = block["child_page"]["title"]
                    if week_info in title:
                        logger.info(f"✅ 기존 주차 페이지 발견: {title}")
                        return block["id"]
        except Exception as e:
            logger.warning(f"페이지 검색 중 오류: {e}")
        
        # 새 페이지 생성
        logger.info(f"📝 새 주차 페이지 생성: {week_info}")
        
        new_page = await self.client.pages.create(
            parent={"page_id": self.parent_page_id},
            properties={
                "title": {
                    "title": [{"text": {"content": week_info}}]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"text": {"content": f"📅 {week_info}"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": "이번 주 공모전 작명 추천 목록입니다."}}]
                    }
                },
                {
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                }
            ]
        )
        
        logger.info(f"✅ 주차 페이지 생성 완료: {new_page['id']}")
        return new_page["id"]
    
    async def create_contest_page(
        self,
        parent_page_id: str,
        contest: ContestInfo,
        top3: List[Submission],
        all_submissions: List[Submission] = None,
    ) -> str:
        """공모전 결과 페이지 생성
        
        Args:
            parent_page_id: 부모(주차) 페이지 ID
            contest: 공모전 정보
            top3: TOP 3 작명
            all_submissions: 전체 후보 작명들 (선택)
            
        Returns:
            생성된 페이지 ID
        """
        logger.info(f"📝 공모전 페이지 생성: {contest['title']}")
        
        # 메달에 따른 작명 블록 생성
        medals = ["🥇", "🥈", "🥉"]
        submission_blocks = []
        
        for i, sub in enumerate(top3[:3]):
            medal = medals[i] if i < len(medals) else "🏅"
            score = sub.get('score', 0) or 0
            
            submission_blocks.extend([
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": f"{medal} {sub['name']}"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": sub['description']}}]
                    }
                },
                {
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": [
                            {"text": {"content": f"점수: {score:.1f} | 전략: {sub['strategy']} | 모델: {sub['provider']}/{sub['model']}"}}
                        ],
                        "icon": {"emoji": "📊"}
                    }
                },
            ])
        
        # 페이지 생성
        new_page = await self.client.pages.create(
            parent={"page_id": parent_page_id},
            properties={
                "title": {
                    "title": [{"text": {"content": contest['title']}}]
                }
            },
            children=[
                # 공모전 정보 헤더
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"text": {"content": f"🏆 {contest['title']}"}}]
                    }
                },
                # 공모전 기본 정보
                {
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": [
                            {"text": {"content": f"🏢 주최: {contest['held_by']}\n📅 마감: {contest.get('deadline', '미정')}\n🔗 "}, },
                            {"text": {"content": "공모전 링크", "link": {"url": contest['url']}}},
                        ],
                        "icon": {"emoji": "📌"}
                    }
                },
                # 제출방법
                {
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [{"text": {"content": "📝 제출방법"}}],
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [{"text": {"content": contest['submission_method']}}]
                                }
                            }
                        ]
                    }
                },
                # 구분선
                {
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                },
                # 추천 작명 섹션 제목
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"text": {"content": "🎯 추천 작명 TOP 3"}}]
                    }
                },
                # TOP 3 작명들
                *submission_blocks,
            ]
        )
        
        # 전체 후보 작명 섹션 추가 (있는 경우)
        if all_submissions and len(all_submissions) > 3:
            # 페이지에 블록 추가
            all_candidates_blocks = [
                {
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": f"📋 전체 후보 작명 ({len(all_submissions)}개)"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [{"text": {"content": "펼쳐서 전체 후보 보기"}}],
                        "children": []
                    }
                },
            ]
            
            # 토글 안에 들어갈 후보들 (TOP 3 제외, 최대 50개)
            top3_names = {s['name'] for s in top3[:3]}
            candidates_text = []
            for i, sub in enumerate(all_submissions[3:50], 4):
                score = sub.get('score', 0) or 0
                strategy = sub.get('strategy', 'Unknown')
                provider = sub.get('provider', 'Unknown')
                candidates_text.append(f"{i}. {sub['name']} (점수: {score:.0f}, 전략: {strategy}, {provider})")
            
            # 토글 children에 텍스트 블록 추가
            if candidates_text:
                all_candidates_blocks[2]["toggle"]["children"] = [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": "\n".join(candidates_text[:20])}}]
                        }
                    }
                ]
                # 나머지가 있으면 추가 블록
                if len(candidates_text) > 20:
                    all_candidates_blocks[2]["toggle"]["children"].append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": "\n".join(candidates_text[20:40])}}]
                        }
                    })
            
            await self.client.blocks.children.append(
                block_id=new_page["id"],
                children=all_candidates_blocks
            )
        
        # 푸터 추가
        await self.client.blocks.children.append(
            block_id=new_page["id"],
            children=[
                {
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"text": {"content": f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 🤖 Fast-Naming AI Agent"}}
                        ]
                    }
                },
            ]
        )
        
        logger.info(f"✅ 공모전 페이지 생성 완료: {new_page['id']}")
        return new_page["id"]
    
    async def get_processed_contest_urls(self) -> List[str]:
        """이미 처리된 공모전 URL 목록 조회 (중복 방지용)
        
        두 가지 방법으로 중복 체크:
        1. URL 기반: 페이지 내 callout에서 wevity.com URL 추출
        2. 제목 기반: 공모전 페이지 제목으로 fallback
        """
        logger.info("🔍 기존 처리된 공모전 조회")
        
        processed_urls = []
        processed_titles = []  # 제목 기반 fallback
        
        try:
            # 부모 페이지의 모든 하위 페이지 조회
            children = await self.client.blocks.children.list(
                block_id=self.parent_page_id
            )
            
            for week_block in children.get("results", []):
                if week_block["type"] == "child_page":
                    week_page_id = week_block["id"]
                    
                    # 주차 페이지의 하위 페이지 (공모전 페이지) 조회
                    try:
                        week_children = await self.client.blocks.children.list(
                            block_id=week_page_id
                        )
                    except Exception as e:
                        logger.warning(f"주차 페이지 조회 실패: {e}")
                        continue
                    
                    for contest_block in week_children.get("results", []):
                        if contest_block["type"] == "child_page":
                            # 공모전 페이지 제목 저장 (fallback용)
                            contest_title = contest_block["child_page"].get("title", "")
                            if contest_title:
                                processed_titles.append(contest_title)
                            
                            # 공모전 페이지 내용에서 URL 추출
                            contest_page_id = contest_block["id"]
                            try:
                                page_content = await self.client.blocks.children.list(
                                    block_id=contest_page_id
                                )
                                
                                for block in page_content.get("results", []):
                                    # callout 블록에서 URL 추출
                                    if block["type"] == "callout":
                                        rich_text = block["callout"].get("rich_text", [])
                                        for text_item in rich_text:
                                            if "link" in text_item.get("text", {}):
                                                url = text_item["text"]["link"].get("url", "")
                                                if "wevity.com" in url:
                                                    processed_urls.append(url)
                                    
                                    # bookmark 블록에서도 URL 추출 (구조 변경 대비)
                                    elif block["type"] == "bookmark":
                                        url = block["bookmark"].get("url", "")
                                        if "wevity.com" in url:
                                            processed_urls.append(url)
                            
                            except Exception as e:
                                logger.debug(f"페이지 내용 조회 실패: {e}")
        
        except Exception as e:
            logger.warning(f"기존 URL 조회 중 오류: {e}")
        
        # 중복 제거
        processed_urls = list(set(processed_urls))
        
        logger.info(f"📊 기존 처리된 공모전: URL {len(processed_urls)}개, 제목 {len(processed_titles)}개")
        
        # 제목 목록을 인스턴스 변수에 저장 (나중에 제목 기반 중복 체크에 사용)
        self._processed_titles = processed_titles
        
        return processed_urls


async def save_to_notion(
    contest: ContestInfo,
    top3: List[Submission],
    week_info: str,
    all_submissions: List[Submission] = None,
) -> Optional[str]:
    """Notion에 결과 저장
    
    Args:
        all_submissions: 전체 후보 작명들 (선택)
    
    Returns:
        성공 시 Notion 페이지 URL, 실패 시 None
    """
    
    try:
        saver = NotionSaver()
        
        # 1. 주차 페이지 찾기/생성
        week_page_id = await saver.find_or_create_week_page(week_info)
        
        # 2. 공모전 페이지 생성 (전체 후보 포함)
        page_id = await saver.create_contest_page(week_page_id, contest, top3, all_submissions)
        
        # Notion 페이지 URL 생성
        # page_id 형식: 2cf86726-d532-81f6-949b-c5d7fe570645
        # URL 형식: https://notion.so/2cf86726d53281f6949bc5d7fe570645
        clean_id = page_id.replace("-", "")
        notion_url = f"https://notion.so/{clean_id}"
        
        logger.info(f"✅ Notion 저장 완료: {notion_url}")
        return notion_url
        
    except Exception as e:
        logger.error(f"❌ Notion 저장 실패: {e}")
        return None


async def get_processed_urls() -> List[str]:
    """이미 처리된 공모전 URL 목록 조회"""
    try:
        saver = NotionSaver()
        return await saver.get_processed_contest_urls()
    except Exception as e:
        logger.error(f"❌ 처리된 URL 조회 실패: {e}")
        return []


# 테스트용
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        # 기존 처리된 URL 조회 테스트
        urls = await get_processed_urls()
        print(f"처리된 URL: {len(urls)}개")
        for url in urls[:5]:
            print(f"  - {url}")
    
    asyncio.run(main())
