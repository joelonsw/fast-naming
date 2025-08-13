import logging
import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Union, List, Dict, Optional
from contest_processor import create_contest_processor

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Mount static files
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    return {"message": "Hello World"}

class Item(BaseModel):
    name: str
    price: float
    is_offer: Union[bool, None] = None

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

@app.get("/users/me")
async def read_user_me():
    return {"username": "me"}

@app.get("/users/{user_id}")
async def read_user(user_id: int):
    return {"user_id": user_id}

# Contest submission endpoints
class ContestRequest(BaseModel):
    contestTitle: str
    contestContent: str
    contestHeldBy: str
    contestType: str  # "슬로건" or "네이밍"
    contestHeldByType: str  # "공공기관", "사기업", "학교"
    contestCriteria: Optional[Dict[str, int]] = None

class ContestResponse(BaseModel):
    success: bool
    message: str
    result_file: Optional[str] = None
    total_submissions: Optional[int] = None
    statistics: Optional[Dict] = None

@app.post("/name", response_model=ContestResponse)
async def generate_contest_submissions(request: ContestRequest):
    """Generate contest submissions using multiple LLM providers."""
    logger.info("🚀 POST /name API 호출 시작")
    logger.info(f"📝 요청 데이터: contestTitle={request.contestTitle}, contestType={request.contestType}, contestHeldByType={request.contestHeldByType}")
    
    try:
        logger.info("🔍 1단계: 요청 데이터 유효성 검증 시작")
        
        # Validate contest type
        if request.contestType not in ["슬로건", "네이밍"]:
            logger.error(f"❌ contestType 유효성 검증 실패: {request.contestType}")
            raise HTTPException(status_code=400, detail="contestType must be '슬로건' or '네이밍'")
        
        # Validate held by type
        if request.contestHeldByType not in ["공공기관", "사기업", "학교"]:
            logger.error(f"❌ contestHeldByType 유효성 검증 실패: {request.contestHeldByType}")
            raise HTTPException(status_code=400, detail="contestHeldByType must be '공공기관', '사기업', or '학교'")
        
        logger.info("✅ 요청 데이터 유효성 검증 완료")
        
        logger.info("🔧 2단계: Contest Processor 생성 시작")
        # Create contest processor
        processor = create_contest_processor()
        logger.info("✅ Contest Processor 생성 완료")
        
        logger.info("📊 3단계: 요청 데이터 변환")
        # Convert request to dict
        contest_data = {
            "contestTitle": request.contestTitle,
            "contestContent": request.contestContent,
            "contestHeldBy": request.contestHeldBy,
            "contestType": request.contestType,
            "contestHeldByType": request.contestHeldByType,
            "contestCriteria": request.contestCriteria or {}
        }
        logger.info(f"📋 변환된 데이터: {contest_data}")
        
        logger.info("🎯 4단계: 작명 생성 시작")
        # Generate submissions
        result = processor.generate_submissions(contest_data)
        logger.info("✅ 작명 생성 완료")
        
        if "error" in result:
            logger.error(f"❌ 작명 생성 중 오류 발생: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])
        
        logger.info("📈 5단계: 통계 정보 생성")
        # Get statistics
        statistics = processor.get_statistics(result)
        logger.info(f"📊 통계 정보: {statistics}")
        
        logger.info("💾 6단계: 응답 생성")
        response = ContestResponse(
            success=True,
            message="Contest submissions generated successfully",
            result_file=f"result/result{processor.result_counter-1:04d}.json",
            total_submissions=result["total_submissions"],
            statistics=statistics
        )
        
        logger.info(f"🎉 API 호출 완료! 총 {result['total_submissions']}개의 작명 생성됨")
        return response
        
    except HTTPException:
        logger.error("❌ HTTPException 발생")
        raise
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate submissions: {str(e)}")

@app.get("/name/status")
async def get_generation_status():
    """Get status of submission generation."""
    try:
        processor = create_contest_processor()
        return {
            "status": "ready",
            "available_providers": list(processor.llm_orchestrator.clients.keys()),
            "examples_loaded": len(processor.examples_data)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.post("/name/debug")
async def debug_contest_request(request: ContestRequest):
    """Debug endpoint to test request validation."""
    return {
        "success": True,
        "received_data": {
            "contestTitle": request.contestTitle,
            "contestContent": request.contestContent,
            "contestHeldBy": request.contestHeldBy,
            "contestType": request.contestType,
            "contestHeldByType": request.contestHeldByType,
            "contestCriteria": request.contestCriteria
        }
    }

@app.post("/name/test-llm")
async def test_llm_generation(request: ContestRequest):
    """Test LLM generation with a single call."""
    try:
        from llm_clients import create_llm_orchestrator
        from contest_processor import create_contest_processor
        
        logger.info("🧪 LLM 테스트 시작")
        
        # Create processor
        processor = create_contest_processor()
        
        # Convert request to dict
        contest_data = {
            "contestTitle": request.contestTitle,
            "contestContent": request.contestContent,
            "contestHeldBy": request.contestHeldBy,
            "contestType": request.contestType,
            "contestHeldByType": request.contestHeldByType,
            "contestCriteria": request.contestCriteria or {}
        }
        
        # Extract examples
        successful_examples = processor.extract_successful_examples(contest_data)
        
        # Test with Groq only
        orchestrator = create_llm_orchestrator()
        if "groq" in orchestrator.clients:
            client = orchestrator.clients["groq"]["client"]
            model = orchestrator.clients["groq"]["models"][0]
            
            # Create prompts
            system_prompt = orchestrator._create_system_prompt(contest_data)
            user_prompt = orchestrator._create_user_prompt(contest_data, successful_examples)
            
            logger.info("🤖 Groq API 호출 테스트")
            response = client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                temperature=0.7,
                top_p=0.9,
                max_tokens=8192
            )
            
            # Parse response
            submissions = orchestrator._parse_response(response)
            valid_submissions = orchestrator._validate_submissions(submissions)
            
            return {
                "success": True,
                "raw_response": response,
                "parsed_submissions": submissions,
                "valid_submissions": valid_submissions,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt
            }
        else:
            return {"success": False, "error": "Groq client not available"}
            
    except Exception as e:
        logger.error(f"❌ LLM 테스트 실패: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

# Frontend routes
@app.get("/result/{result_number}")
async def get_result_page(result_number: int):
    """Serve the frontend HTML page for viewing results."""
    try:
        # Check if frontend directory exists
        if not os.path.exists("frontend"):
            raise HTTPException(status_code=404, detail="Frontend not found")
        
        # Check if the HTML file exists
        html_path = "frontend/index.html"
        if not os.path.exists(html_path):
            raise HTTPException(status_code=404, detail="Frontend page not found")
        
        return FileResponse(html_path, media_type="text/html")
        
    except Exception as e:
        logger.error(f"Error serving frontend: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/result/{result_number}")
async def get_result_data(result_number: int):
    """Get result data for the frontend."""
    try:
        # Construct the result file path
        result_file = f"result/result{result_number:04d}.json"
        
        # Check if the result file exists
        if not os.path.exists(result_file):
            raise HTTPException(status_code=404, detail=f"Result {result_number} not found")
        
        # Read and return the result data
        with open(result_file, 'r', encoding='utf-8') as f:
            result_data = json.load(f)
        
        logger.info(f"✅ Result {result_number} data served successfully")
        return result_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading result {result_number}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
