"""
Slack 알림 모듈
Incoming Webhook을 사용하여 TOP 3 결과 전송
"""

import os
import httpx
import logging
from typing import List

from state import ContestInfo, Submission

logger = logging.getLogger(__name__)


async def send_slack_notification(
    contest: ContestInfo,
    top3: List[Submission],
    notion_url: str = None,
) -> bool:
    """TOP 3 결과를 Slack으로 전송"""
    
    webhook_url = os.getenv("SLACK_WEBHOOK")
    if not webhook_url:
        logger.error("❌ SLACK_WEBHOOK 환경변수가 설정되지 않았습니다")
        return False
    
    logger.info(f"📤 Slack 알림 전송: {contest['title']}")
    
    # 메달 이모지
    medals = ["🥇", "🥈", "🥉"]
    
    # Slack Block Kit 메시지 구성
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🏆 공모전 작명 추천",
                "emoji": True
            }
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*📌 공모전명:*\n{contest['title']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*🏢 주최기관:*\n{contest['held_by']}"
                },
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📋 공모전 내용:*\n{contest['content'][:500]}..."
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*🔗 링크:*\n<{contest['url']}|공모전 바로가기>"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*📝 제출방법:*\n{contest['submission_method'][:200]}"
                },
            ]
        },
    ]
    
    # Notion 링크 추가 (있는 경우)
    if notion_url:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📒 Notion 상세 페이지:*\n<{notion_url}|Notion에서 보기>"
            }
        })
    
    blocks.extend([
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*🎯 추천 작명 TOP 3*"
            }
        },
    ])
    # TOP 3 작명 추가
    for i, sub in enumerate(top3[:3]):
        medal = medals[i] if i < len(medals) else "🏅"
        score = sub.get('score', 0) or 0
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{medal} *{sub['name']}*\n_{sub['description']}_\n`점수: {score:.1f}` | `전략: {sub['strategy']}`"
            }
        })
    
    # 푸터
    blocks.extend([
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"⏰ 마감: {contest.get('deadline', '미정')} | 🤖 Fast-Naming AI Agent"
                }
            ]
        }
    ])
    
    payload = {"blocks": blocks}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            
        logger.info("✅ Slack 알림 전송 성공")
        return True
        
    except Exception as e:
        logger.error(f"❌ Slack 알림 전송 실패: {e}")
        return False


# 테스트용
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        test_contest = ContestInfo(
            title="테스트 공모전",
            content="테스트 공모전 내용입니다.",
            held_by="테스트 기관",
            contest_type="네이밍",
            held_by_type="공공기관",
            url="https://example.com",
            submission_method="이메일 제출: test@example.com",
            deadline="2024-12-31",
            d_day="D-10",
        )
        
        test_submissions = [
            Submission(
                name="테스트 작명 1",
                description="첫 번째 테스트 작명입니다.",
                strategy="Keyword Combination",
                provider="gemini",
                model="gemini-2.0-flash",
                score=95.0,
                criteria_scores={"창의성": 25, "적합성": 25, "기억용이성": 23, "완성도": 22},
            ),
            Submission(
                name="테스트 작명 2",
                description="두 번째 테스트 작명입니다.",
                strategy="Metaphor & Analogy",
                provider="groq",
                model="openai/gpt-oss-120b",
                score=88.0,
                criteria_scores={"창의성": 23, "적합성": 22, "기억용이성": 22, "완성도": 21},
            ),
            Submission(
                name="테스트 작명 3",
                description="세 번째 테스트 작명입니다.",
                strategy="Simple & Direct",
                provider="gemini",
                model="gemini-2.0-flash",
                score=82.0,
                criteria_scores={"창의성": 20, "적합성": 22, "기억용이성": 20, "완성도": 20},
            ),
        ]
        
        result = await send_slack_notification(test_contest, test_submissions)
        print(f"Slack 전송 결과: {result}")
    
    asyncio.run(main())
