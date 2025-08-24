import logging
import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
from typing import Union, List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
from contest_processor import create_async_contest_processor
# from evaluator import create_contest_evaluator
from evaluator_with_search import create_evaluator_with_search
from evaluator import create_contest_evaluator

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

# CORS 미들웨어 설정
origins = [
    "http://joelonname.kro.kr",
    "https://joelonname.kro.kr",
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    """Serve the home page for contest submission."""
    try:
        # Check if frontend directory exists
        if not os.path.exists("frontend"):
            raise HTTPException(status_code=404, detail="Frontend not found")
        
        # Check if the home HTML file exists
        html_path = "frontend/home.html"
        if not os.path.exists(html_path):
            raise HTTPException(status_code=404, detail="Home page not found")
        
        return FileResponse(html_path, media_type="text/html")
        
    except Exception as e:
        logger.error(f"Error serving home page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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
    contestType: str  # "슬로건" or "네이밍" or "마스코트"
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
        if request.contestType not in ["슬로건", "네이밍", "마스코트"]:
            logger.error(f"❌ contestType 유효성 검증 실패: {request.contestType}")
            raise HTTPException(status_code=400, detail="contestType must be '슬로건' or '네이밍' or '마스코트")
        
        # Validate held by type
        if request.contestHeldByType not in ["공공기관", "사기업", "학교"]:
            logger.error(f"❌ contestHeldByType 유효성 검증 실패: {request.contestHeldByType}")
            raise HTTPException(status_code=400, detail="contestHeldByType must be '공공기관', '사기업', or '학교'")
        
        logger.info("✅ 요청 데이터 유효성 검증 완료")
        
        logger.info("🔧 2단계: Contest Processor 생성 시작")
        # Create contest processor
        # processor = create_contest_processor()
        processor = create_async_contest_processor()
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
        # result = processor.generate_submissions(contest_data)
        result = await processor.generate_submissions(contest_data)
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
        # processor = create_contest_processor()
        processor = create_async_contest_processor()
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
        from async_llm_client import create_async_llm_orchestrator
        from contest_processor import create_async_contest_processor
        # from evaluator import create_contest_evaluator
        from evaluator_with_search import create_evaluator_with_search
        
        logger.info("🧪 LLM 테스트 시작")
        
        # Create processor
        # processor = create_contest_processor()
        processor = create_async_contest_processor()
        
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
        # orchestrator = create_llm_orchestrator()
        orchestrator = create_async_llm_orchestrator()
        if "groq" in orchestrator.clients:
            client = orchestrator.clients["groq"]["client"]
            model = orchestrator.clients["groq"]["models"][0]
            
            # Create prompts
            system_prompt = orchestrator._create_system_prompt(contest_data)
            user_prompt = orchestrator._create_user_prompt(contest_data, successful_examples)
            
            logger.info("🤖 Groq API 호출 테스트")
            # response = client.generate(
            response = await client.generate(
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

# Refinement endpoint
class RefinementRequest(BaseModel):
    result_number: str
    selected_submissions: List[Dict[str, str | int | float | None]]
    refinement_instruction: str

@app.post("/api/refine")
async def refine_submissions_endpoint(request: RefinementRequest):
    """Refines selected submissions based on user feedback."""
    try:
        processor = create_async_contest_processor()
        result = await processor.refine_submissions(
            result_number=request.result_number,
            selected_submissions=request.selected_submissions,
            refinement_instruction=request.refinement_instruction
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return result
    except Exception as e:
        logger.error(f"❌ Refinement failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Frontend routes
@app.get("/result/{result_number}")
async def get_result_page(result_number: str):
    """Serve the frontend HTML page for viewing results."""
    try:
        # Check if frontend directory exists
        if not os.path.exists("frontend"):
            raise HTTPException(status_code=404, detail="Frontend not found")
        
        # Check if the HTML file exists
        html_path = "frontend/result.html"
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

# Evaluation endpoints
class EvaluationRequest(BaseModel):
    result_number: int

class EvaluationResponse(BaseModel):
    success: bool
    message: str
    score_file: Optional[str] = None
    total_submissions: Optional[int] = None
    evaluation_criteria: Optional[Dict[str, int]] = None

async def _perform_web_search(query: str) -> List[str]:
    """Performs a web search using httpx and BeautifulSoup to get snippets."""
    try:
        async with httpx.AsyncClient() as client:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
            response = await client.get(f"https://html.duckduckgo.com/html/?q={query}", headers=headers, follow_redirects=True)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        snippets = [a.text for a in soup.find_all('a', class_='result__snippet')]
        return snippets[:3] # Return top 3 snippets
    except Exception as e:
        logger.error(f"❌ Web search failed for query '{query}': {e}")
        return []

@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_contest_submissions(request: EvaluationRequest):
    """Evaluate contest submissions using LLM-based scoring."""
    logger.info(f"🎯 POST /evaluate API 호출 시작: result_number={request.result_number}")
    
    try:
        # Load the result file
        result_file = f"result/result{request.result_number:04d}.json"
        
        if not os.path.exists(result_file):
            logger.error(f"❌ Result file not found: {result_file}")
            raise HTTPException(status_code=404, detail=f"Result {request.result_number} not found")
        
        logger.info(f"📂 1단계: 결과 파일 로드 시작: {result_file}")
        with open(result_file, 'r', encoding='utf-8') as f:
            result_data = json.load(f)
        
        contest_data = result_data.get('contest_data', {})
        submissions = result_data.get('submissions', [])
        
        if not submissions:
            logger.error("❌ No submissions found in result file")
            raise HTTPException(status_code=400, detail="No submissions found in result file")
        
        logger.info(f"✅ 결과 파일 로드 완료: {len(submissions)}개 작명")
        
        # Create evaluator
        logger.info("🔧 2단계: 평가기 생성 시작")
        evaluator = create_contest_evaluator()
        logger.info("✅ 평가기 생성 완료")
        
        # Check if criteria already exists
        existing_criteria = contest_data.get('contestCriteria')
        
        # Generate evaluation criteria if not exists
        logger.info("📊 3단계: 평가 기준 생성 시작")
        if existing_criteria:
            criteria = existing_criteria
            logger.info(f"✅ 기존 평가 기준 사용: {criteria}")
        else:
            criteria = evaluator.generate_criteria(
                contest_data.get('contestTitle', ''),
                contest_data.get('contestContent', '')
            )
            logger.info(f"✅ 새로운 평가 기준 생성: {criteria}")
        
        # Evaluate submissions
        logger.info("🎯 4단계: 작명 평가 시작")
        evaluated_submissions = evaluator.evaluate_submissions(
            contest_data.get('contestTitle', ''),
            contest_data.get('contestContent', ''),
            submissions,
            criteria
        )
        
        # Save evaluation results
        logger.info("💾 5단계: 평가 결과 저장 시작")
        score_file = evaluator.save_evaluation_result(
            request.result_number,
            evaluated_submissions,
            criteria,
            contest_data
        )
        logger.info(f"✅ 평가 결과 저장 완료: {score_file}")
        
        # Calculate statistics
        total_score = sum(sub.get('total_score', 0) for sub in evaluated_submissions)
        avg_score = total_score / len(evaluated_submissions) if evaluated_submissions else 0
        
        logger.info(f"📈 6단계: 통계 생성 완료 - 총점: {total_score}, 평균: {avg_score:.2f}")
        
        # Return response
        response = EvaluationResponse(
            success=True,
            message="Contest submissions evaluated successfully",
            score_file=score_file,
            total_submissions=len(evaluated_submissions),
            evaluation_criteria=criteria
        )
        
        logger.info(f"🎉 평가 완료! {len(evaluated_submissions)}개 작명 평가됨")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 평가 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to evaluate submissions: {str(e)}")

@app.get("/api/score/{score_number}")
async def get_score_data(score_number: int):
    """Get score data for the frontend."""
    try:
        # Construct the score file path
        score_file = f"result/score{score_number:04d}.json"
        
        # Check if the score file exists
        if not os.path.exists(score_file):
            raise HTTPException(status_code=404, detail=f"Score {score_number} not found")
        
        # Read and return the score data
        with open(score_file, 'r', encoding='utf-8') as f:
            score_data = json.load(f)
        
        logger.info(f"✅ Score {score_number} data served successfully")
        return score_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading score {score_number}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
