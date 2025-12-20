"""
Wevity 공모전 스크래핑 모듈 (Playwright 버전)
실제 브라우저를 사용하여 봇 감지 우회
"""

from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
from typing import List, Optional
import re
import logging
import asyncio

from state import ContestInfo

logger = logging.getLogger(__name__)

# Wevity 네이밍/슬로건 공모전 목록 (접수중만)
WEVITY_LIST_URL = "https://www.wevity.com/?c=find&s=1&gub=1&cidx=25&mode=ing"
WEVITY_BASE_URL = "https://www.wevity.com/"


async def get_page_content(url: str, browser: Browser) -> str:
    """Playwright를 사용하여 페이지 콘텐츠 가져오기"""
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # 페이지 로딩 대기
        await page.wait_for_timeout(2000)
        content = await page.content()
        return content
    finally:
        await page.close()


async def scrape_contest_list() -> List[str]:
    """접수중인 공모전 목록의 상세 페이지 URL들을 수집"""
    logger.info("🔍 Wevity 접수중 공모전 목록 스크래핑 시작 (Playwright)")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        try:
            html = await get_page_content(WEVITY_LIST_URL, browser)
            soup = BeautifulSoup(html, 'html.parser')
            
            # 공모전 목록에서 상세 페이지 링크 추출
            contest_urls = []
            
            # ul.list 내의 a[href*="gbn=view"] 링크 찾기
            list_container = soup.select_one('ul.list')
            if list_container:
                links = list_container.select('a[href*="gbn=view"]')
                for link in links:
                    href = link.get('href', '')
                    if href:
                        # 상대 URL을 절대 URL로 변환
                        if href.startswith('?'):
                            full_url = WEVITY_BASE_URL + href
                        elif not href.startswith('http'):
                            full_url = WEVITY_BASE_URL + href
                        else:
                            full_url = href
                        
                        # viewok 파라미터가 포함된 URL로 변환
                        full_url = full_url.replace('gbn=view', 'gbn=viewok')
                        
                        if full_url not in contest_urls:
                            contest_urls.append(full_url)
            
            logger.info(f"✅ {len(contest_urls)}개 공모전 발견")
            return contest_urls
            
        finally:
            await browser.close()


async def scrape_contest_detail(url: str, browser: Browser = None) -> Optional[ContestInfo]:
    """개별 공모전 상세 페이지 스크래핑"""
    logger.info(f"📄 공모전 상세 스크래핑: {url}")
    
    should_close_browser = False
    
    try:
        if browser is None:
            p = await async_playwright().start()
            browser = await p.chromium.launch(headless=True)
            should_close_browser = True
        
        html = await get_page_content(url, browser)
        soup = BeautifulSoup(html, 'html.parser')
        
        # 제목 추출
        title_elem = soup.select_one('div.tit-area h6.tit')
        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
        
        # D-Day 정보
        d_day_elem = soup.select_one('.d-day')
        d_day = d_day_elem.get_text(strip=True) if d_day_elem else None
        
        # 공모전 정보 (분야, 주최/주관, 접수기간 등)
        info_dict = {}
        info_list = soup.select('ul.cd-info-list li')
        for li in info_list:
            label_elem = li.select_one('span.tit')
            if label_elem:
                label = label_elem.get_text(strip=True)
                # 레이블을 제거한 나머지 텍스트가 값
                value = li.get_text(strip=True).replace(label, '').strip()
                info_dict[label] = value
        
        # 상세 내용
        content_elem = soup.select_one('div.comm-desc')
        content = content_elem.get_text(separator='\n', strip=True) if content_elem else ""
        
        # 주최/주관 추출
        held_by = info_dict.get('주최/주관', info_dict.get('주최', '알 수 없음'))
        
        # 분야에서 contest_type 추출
        field = info_dict.get('분야', '')
        contest_type = detect_contest_type(field, title, content)
        
        # 기관 유형 추측
        held_by_type = detect_held_by_type(held_by, content)
        
        # 제출방법 추출
        submission_method = extract_submission_method(content)
        
        # 마감일 추출
        deadline = info_dict.get('접수기간', '')
        
        contest_info = ContestInfo(
            title=title,
            content=content[:3000],  # 너무 긴 내용은 잘라냄
            held_by=held_by,
            contest_type=contest_type,
            held_by_type=held_by_type,
            url=url,
            submission_method=submission_method,
            deadline=deadline,
            d_day=d_day,
        )
        
        logger.info(f"✅ 스크래핑 완료: {title}")
        return contest_info
        
    except Exception as e:
        logger.error(f"❌ 스크래핑 실패 ({url}): {e}")
        return None
    
    finally:
        if should_close_browser and browser:
            await browser.close()


def detect_contest_type(field: str, title: str, content: str) -> str:
    """분야, 제목, 내용에서 공모전 유형 감지"""
    text = (field + title + content).lower()
    
    if '슬로건' in text or '캐치프레이즈' in text:
        return '슬로건'
    elif '네이밍' in text or '명칭' in text or '이름' in text or '브랜드명' in text:
        return '네이밍'
    elif '마스코트' in text or '캐릭터' in text:
        return '마스코트'
    else:
        return '네이밍'  # 기본값


def detect_held_by_type(held_by: str, content: str) -> str:
    """주최기관 유형 감지"""
    text = (held_by + content).lower()
    
    public_keywords = ['공사', '공단', '시청', '구청', '도청', '군청', '정부', '부처', '원', 
                       '재단', '협회', '센터', '진흥원', '연구원', '개발공사', '시', '구', '도', '군']
    school_keywords = ['대학', '학교', '교육', '학생']
    
    for keyword in public_keywords:
        if keyword in text:
            return '공공기관'
    
    for keyword in school_keywords:
        if keyword in text:
            return '학교'
    
    return '사기업'


def extract_submission_method(content: str) -> str:
    """내용에서 제출방법 추출"""
    # 제출방법 관련 섹션 찾기
    patterns = [
        r'(?:제출|접수|응모)\s*(?:방법|방식)[:\s]*(.+?)(?:\n|$)',
        r'(?:■|●|▶)\s*(?:제출|접수|응모)\s*(?:방법|방식)(.+?)(?:■|●|▶|$)',
        r'(?:응모|제출)\s*(?:방법|방식)\s*[:\-]\s*(.+?)(?:\n\n|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            method = match.group(1).strip()
            # 너무 긴 경우 첫 200자만
            if len(method) > 300:
                method = method[:300] + "..."
            return method
    
    # 패턴으로 찾지 못한 경우, 이메일이나 URL 찾기
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', content)
    if email_match:
        return f"이메일 제출: {email_match.group()}"
    
    return "상세 내용 참조"


async def scrape_all_contests(exclude_urls: List[str] = None) -> List[ContestInfo]:
    """모든 접수중 공모전 스크래핑 (중복 제외)"""
    exclude_urls = exclude_urls or []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        try:
            # 목록 페이지에서 URL 수집
            logger.info("🔍 Wevity 접수중 공모전 목록 스크래핑 시작 (Playwright)")
            
            html = await get_page_content(WEVITY_LIST_URL, browser)
            soup = BeautifulSoup(html, 'html.parser')
            
            contest_urls = []
            list_container = soup.select_one('ul.list')
            if list_container:
                links = list_container.select('a[href*="gbn=view"]')
                for link in links:
                    href = link.get('href', '')
                    if href:
                        if href.startswith('?'):
                            full_url = WEVITY_BASE_URL + href
                        elif not href.startswith('http'):
                            full_url = WEVITY_BASE_URL + href
                        else:
                            full_url = href
                        
                        full_url = full_url.replace('gbn=view', 'gbn=viewok')
                        
                        if full_url not in contest_urls:
                            contest_urls.append(full_url)
            
            logger.info(f"✅ {len(contest_urls)}개 공모전 발견")
            
            # 이미 처리한 URL 제외
            new_urls = [url for url in contest_urls if url not in exclude_urls]
            logger.info(f"📊 새로운 공모전: {len(new_urls)}개 (총 {len(contest_urls)}개 중)")
            
            # 각 공모전 상세 스크래핑
            contests = []
            for url in new_urls:
                contest = await scrape_contest_detail(url, browser)
                if contest:
                    contests.append(contest)
                # 각 요청 사이에 약간의 지연
                await asyncio.sleep(1)
            
            return contests
            
        finally:
            await browser.close()


# 테스트용
if __name__ == "__main__":
    import asyncio
    
    async def main():
        logging.basicConfig(level=logging.INFO)
        contests = await scrape_all_contests()
        for c in contests:
            print(f"\n{'='*50}")
            print(f"제목: {c['title']}")
            print(f"주최: {c['held_by']}")
            print(f"유형: {c['contest_type']} / {c['held_by_type']}")
            print(f"제출방법: {c['submission_method']}")
            print(f"URL: {c['url']}")
    
    asyncio.run(main())
