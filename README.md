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
- **Gemini + Groq** LLM으로 작명 생성
- **Slack** 알림 및 **Notion** 결과 저장
- 중복 처리 방지 (이미 처리한 공모전 제외)
