# Fast-Naming

AI 기반 네이밍/슬로건 공모전 작명 자동화 프로젝트

---

## 📁 web/

**배포 URL**: https://accurate-inge-joelonsw-180a8ed4.koyeb.app/

사용자가 직접 공모전 정보를 입력하면 AI가 작명을 생성하고 평가하는 웹 애플리케이션.

- **FastAPI** 백엔드 + **HTML/CSS/JS** 프론트엔드
- 다중 LLM 활용 (Gemini, Groq, GitHub AI, Together AI)
- 6가지 창의적 전략으로 작명 생성
- AI 기반 자동 평가 및 순위 결정

---

## 🤖 agent/

**실행**: GitHub Actions (3일마다 한국시간 22:00)

Wevity 공모전 사이트를 자동으로 스크래핑하여 작명을 생성하고 알림을 보내는 AI Agent.

- **Playwright** 기반 웹 스크래핑
- **Gemini + Groq + GitHub AI** LLM으로 작명 생성
- **8가지 창의적 전략** (한국어 특화 포함)
- **Slack** 알림 및 **Notion** 결과 저장
- 중복 처리 방지 (이미 처리한 공모전 제외)

### 🔄 Agent 워크플로우

```mermaid
flowchart LR
    subgraph Scrape["1. 스크래핑"]
        A[Wevity 접속] --> B[공모전 목록 수집]
        B --> C[상세 정보 파싱]
    end
    
    subgraph Generate["2. 작명 생성"]
        D[Few-shot 예시 로드] --> E[다중 LLM 호출]
        E --> F[8가지 전략 적용]
    end
    
    subgraph Quality["3. 품질 향상"]
        G[중복 제거] --> H[다양성 보장]
        H --> I[TOP 10 정제]
    end
    
    subgraph Evaluate["4. 평가"]
        J[평가 기준 생성] --> K[작명 채점]
        K --> L[TOP 3 선정]
    end
    
    subgraph Notify["5. 알림"]
        M[Notion 저장] --> N[Slack 알림]
    end
    
    Scrape --> Generate --> Quality --> Evaluate --> Notify
```

### 📊 LLM 구성

| 제공자 | 모델 | Rate Limit | 용도 |
|--------|------|:----------:|------|
| **Gemini** | gemini-2.5-flash-lite | 10초 | 작명 생성 |
| **Groq** | openai/gpt-oss-120b | 2초 | 작명 생성 / 평가 |
| **GitHub AI** | openai/gpt-4.1-mini | 10초 | 작명 생성 |

### 📂 Agent 파일 구조

```
agent/
├── main.py              # 메인 실행 파일
├── scraper.py           # Wevity 스크래핑
├── llm_generator.py     # LLM 작명 생성
├── evaluator.py         # 작명 평가
├── refiner.py           # 품질 향상 (중복 제거, 정제)
├── slack_notifier.py    # Slack 알림
├── notion_saver.py      # Notion 저장
├── examples_loader.py   # Few-shot 예시 로드
├── state.py             # 타입 정의
└── langgraph-guide.md   # 상세 가이드
```

---

## 🔐 환경 변수

```env
# LLM API Keys
GEMINI_API_KEY=xxx
GROQ_API_KEY=xxx
GITHUB_TOKEN=xxx

# Slack
SLACK_WEBHOOK=https://hooks.slack.com/services/xxx

# Notion
NOTION_API_KEY=secret_xxx
NOTION_PARENT_PAGE_ID=xxx
```

---

## 📚 참고

- [Agent 상세 가이드](./agent/langgraph-guide.md)
