#!/usr/bin/env python3
"""
Fast-Naming AI Agent LLM API 진단 도구
각 API Key 연동 상태와 라이브러리 호출 안정성, 모델 연결 여부를 원클릭으로 점검합니다.
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# 로컬 임포트 지원을 위해 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from llm_clients import (
    create_generation_clients,
    create_primary_client,
    get_configured_provider_names,
)

# 기본 로깅 비활성화 또는 단순화
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("diagnose")

async def diagnose_single_client(client) -> bool:
    print(f"🔄 진단 중: [{client.provider_name.upper()}] - 모델: {client.model_name}")
    try:
        system_prompt = "당신은 한국어 단어 추천 전문가입니다. 반드시 한 단어만 출력하세요."
        user_prompt = "네이밍 공모전에 쓸 신선한 순우리말 단어 하나만 제안하고 괄호 안에 한글 뜻을 써주세요."
        
        # 15초 타임아웃 적용
        response = await asyncio.wait_for(
            client.generate(system_prompt, user_prompt),
            timeout=15.0
        )
        
        result = response.strip()
        print(f"  🟢 성공: {result}")
        return True
    except asyncio.TimeoutError:
        print(f"  🔴 실패: 응답 시간 초과 (15초 초과)")
        return False
    except Exception as e:
        print(f"  🔴 실패: {e}")
        return False

async def main():
    # .env 파일 경로 지정하여 강제 로드
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(root_dir, ".env")
    load_dotenv(dotenv_path=env_path)
    
    print("=" * 60)
    print("🤖 Fast-Naming LLM API 가용성 종합 진단 도구")
    print("=" * 60)
    
    providers = get_configured_provider_names()
    print(f"📍 설정된 API Provider 리스트: {', '.join(providers) if providers else '없음'}")
    
    if not providers:
        print("❌ [오류] .env 파일에 활성화된 API KEY가 전혀 없습니다!")
        sys.exit(1)
        
    print("-" * 60)
    print("🔍 [Step 1] 개별 Generation 클라이언트 초기화 및 호출 테스트")
    clients = create_generation_clients()
    print(f"👉 초기화된 클라이언트 수: {len(clients)}개\n")
    
    success_count = 0
    for client in clients:
        success = await diagnose_single_client(client)
        if success:
            success_count += 1
        print()
        
    print("-" * 60)
    print("🔍 [Step 2] Primary 클라이언트 검증")
    primary = create_primary_client()
    if primary:
        print(f"👉 지정된 Primary Provider: [{primary.provider_name.upper()}] - 모델: {primary.model_name}")
        primary_success = await diagnose_single_client(primary)
    else:
        print("  🔴 실패: 사용 가능한 Primary 클라이언트를 지정할 수 없습니다.")
        primary_success = False
        
    print("=" * 60)
    print("📊 [진단 종합 결과]")
    print(f"  * 활성 클라이언트 성공율: {success_count}/{len(clients)}")
    print(f"  * Primary 클라이언트 가용성: {'🟢 정상' if primary_success else '🔴 오류'}")
    print("=" * 60)
    
    # 만약 활성화하려 시도한 클라이언트가 있는데 실패했거나, Primary 가용이 안 될 경우 exit code 1 반환
    if success_count < len(clients) or not primary_success or len(clients) == 0:
        print("🚨 [검증 실패] 하나 이상의 LLM 연동에 문제가 발생했습니다. 에러 로그를 확인하세요.")
        sys.exit(1)
    else:
        print("🎉 [검증 통과] 모든 설정된 LLM 클라이언트가 정상 동작합니다!")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
