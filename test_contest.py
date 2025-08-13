"""
Test script for the contest submission generation API.
This script demonstrates how to use the POST /name endpoint.
"""

import requests
import json
import time

# API base URL
BASE_URL = "http://localhost:8000"

def test_contest_submission():
    """Test the contest submission generation."""
    
    # Test data for a naming contest
    contest_data = {
        "contestTitle": "스마트시티 IoT 플랫폼 네이밍 공모전",
        "contestContent": """
        스마트시티 IoT 플랫폼의 브랜드 네이밍을 공모합니다.
        
        요구사항:
        1. 스마트시티의 미래지향적 이미지를 반영
        2. IoT 기술의 연결성과 통합성을 표현
        3. 시민들이 쉽게 기억할 수 있는 이름
        4. 글로벌 시장 진출 가능성 고려
        5. 2-4음절로 구성
        
        대상: 전국민
        주최: 한국정보통신기술협회
        """,
        "contestHeldBy": "한국정보통신기술협회",
        "contestType": "네이밍",
        "contestHeldByType": "사기업",
        "contestCriteria": {
            "창의성": 30,
            "적합성": 25,
            "기억성": 20,
            "확장성": 15,
            "실용성": 10
        }
    }
    
    print("🚀 Testing contest submission generation...")
    print(f"Contest: {contest_data['contestTitle']}")
    print(f"Type: {contest_data['contestType']}")
    print(f"Held by: {contest_data['contestHeldBy']}")
    print("-" * 50)
    
    try:
        # Check API status first
        status_response = requests.get(f"{BASE_URL}/name/status")
        if status_response.status_code == 200:
            status_data = status_response.json()
            print(f"API Status: {status_data['status']}")
            print(f"Available providers: {status_data['available_providers']}")
            print(f"Examples loaded: {status_data['examples_loaded']}")
        else:
            print("Warning: Could not check API status")
        
        print("\n📤 Sending contest submission request...")
        
        # Send the contest submission request
        response = requests.post(
            f"{BASE_URL}/name",
            json=contest_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Success!")
            print(f"Message: {result['message']}")
            print(f"Total submissions: {result['total_submissions']}")
            print(f"Result file: {result['result_file']}")
            
            if result.get('statistics'):
                stats = result['statistics']
                print(f"\n📊 Statistics:")
                print(f"  Provider distribution: {stats['provider_distribution']}")
                print(f"  Model distribution: {stats['model_distribution']}")
                print(f"  Temperature range: {stats['temperature_range']}")
                print(f"  Top-p range: {stats['top_p_range']}")
            
            # Load and display some sample submissions
            try:
                with open(result['result_file'], 'r', encoding='utf-8') as f:
                    full_result = json.load(f)
                
                submissions = full_result.get('submissions', [])
                if submissions:
                    print(f"\n🎯 Sample Submissions (showing first 5):")
                    for i, submission in enumerate(submissions[:5], 1):
                        print(f"  {i}. {submission.get('submission', 'N/A')}")
                        print(f"     Description: {submission.get('description', 'N/A')[:100]}...")
                        print(f"     Provider: {submission.get('provider', 'N/A')}")
                        print(f"     Model: {submission.get('model', 'N/A')}")
                        print()
            
            except Exception as e:
                print(f"Could not load result file: {e}")
        
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Connection error: Make sure the FastAPI server is running on http://localhost:8000")
        print("Run: uvicorn main:app --reload")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_slogan_contest():
    """Test a slogan contest submission."""
    
    slogan_data = {
        "contestTitle": "서울시 환경보호 슬로건 공모전",
        "contestContent": """
        서울시의 환경보호 정책을 알리는 슬로건을 공모합니다.
        
        요구사항:
        1. 환경보호의 중요성을 강조
        2. 시민들의 참여를 유도하는 메시지
        3. 간결하고 기억하기 쉬운 문구
        4. 긍정적이고 희망적인 톤
        5. 20자 이내로 구성
        
        대상: 서울시민
        주최: 서울특별시청
        """,
        "contestHeldBy": "서울특별시청",
        "contestType": "슬로건",
        "contestHeldByType": "공공기관",
        "contestCriteria": {
            "메시지 전달력": 40,
            "창의성": 30,
            "기억성": 20,
            "실용성": 10
        }
    }
    
    print("\n" + "="*60)
    print("🎯 Testing slogan contest submission...")
    print(f"Contest: {slogan_data['contestTitle']}")
    print(f"Type: {slogan_data['contestType']}")
    print(f"Held by: {slogan_data['contestHeldBy']}")
    print("-" * 50)
    
    try:
        response = requests.post(
            f"{BASE_URL}/name",
            json=slogan_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Success!")
            print(f"Total submissions: {result['total_submissions']}")
            print(f"Result file: {result['result_file']}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 Fast Naming Contest API Test")
    print("=" * 60)
    
    # Test naming contest
    test_contest_submission()
    
    # Test slogan contest
    test_slogan_contest()
    
    print("\n" + "="*60)
    print("✅ Test completed!")
    print("Check the 'result' directory for generated JSON files.")
