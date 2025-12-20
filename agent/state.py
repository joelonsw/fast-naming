"""
State definitions for the Fast-Naming LangGraph Agent.
"""

from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime


class ContestInfo(TypedDict):
    """공모전 정보 구조"""
    title: str                    # 공모전명
    content: str                  # 공모전 상세 내용
    held_by: str                  # 주최기관
    contest_type: str             # 네이밍/슬로건
    held_by_type: str             # 공공기관/사기업/학교
    url: str                      # 공모전 링크
    submission_method: str        # 제출방법
    deadline: Optional[str]       # 마감일
    d_day: Optional[str]          # D-Day 정보


class Submission(TypedDict):
    """생성된 작명"""
    name: str                     # 작명
    description: str              # 작명 이유
    strategy: str                 # 사용된 전략
    provider: str                 # LLM 제공자
    model: str                    # 사용된 모델
    score: Optional[float]        # 평가 점수
    criteria_scores: Optional[Dict[str, float]]  # 세부 평가 점수


class NamingAgentState(TypedDict):
    """Agent 전체 상태"""
    # 수집된 공모전들
    contests: List[ContestInfo]
    current_contest_index: int
    
    # 현재 처리중인 공모전
    current_contest: Optional[ContestInfo]
    
    # Few-shot 예시
    successful_examples: List[Dict[str, str]]
    
    # 생성된 작명들
    submissions: List[Submission]
    
    # 평가 결과
    evaluation_criteria: Optional[Dict[str, int]]
    ranked_submissions: List[Submission]
    top3_submissions: List[Submission]
    
    # 실행 메타데이터
    execution_date: str
    week_info: str  # "2024년-12월-3주차" 형식
    
    # 이미 처리한 공모전 (중복 방지)
    processed_contest_urls: List[str]
    
    # 에러 추적
    errors: List[str]
    
    # 알림 전송 결과
    slack_sent: bool
    notion_saved: bool


def create_initial_state() -> NamingAgentState:
    """초기 상태 생성"""
    now = datetime.now()
    week_number = (now.day - 1) // 7 + 1
    week_info = f"{now.year}년-{now.month}월-{week_number}주차"
    
    return NamingAgentState(
        contests=[],
        current_contest_index=0,
        current_contest=None,
        successful_examples=[],
        submissions=[],
        evaluation_criteria=None,
        ranked_submissions=[],
        top3_submissions=[],
        execution_date=now.strftime("%Y-%m-%d"),
        week_info=week_info,
        processed_contest_urls=[],
        errors=[],
        slack_sent=False,
        notion_saved=False,
    )
