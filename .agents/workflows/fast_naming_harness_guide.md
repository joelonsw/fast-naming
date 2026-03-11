---
description: Fast-Naming AI Agent Development Harness Guide
---

# Fast-Naming AI Agent Harness Guide

This document acts as an explicit guideline for any AI Agent working on the Fast-Naming project. Please reference this guide to understand the system architecture, required skills, and agent responsibilities. Adhering to these guidelines ensures no functionality is broken and tasks are properly delegated without hallucination.

## 1. Core Architecture & Sub-Agents

The Fast-Naming system is a multi-agent orchestrated pipeline. Each file in the `agent/` directory corresponds roughly to a specific sub-agent or module:

### **A. Scraper Agent (`scraper.py`)**
- **Responsibility:** Extracts contest details (Title, Type, Held By, URL, Deadline, Submission Method) from Wevity.
- **Key Skill:** Uses `playwright.async_api` to bypass bot detection. Parses specific text (e.g., prepending `[온라인 접수]`, `[구글폼]` tags to `extract_submission_method`).
- **Rule:** DO NOT change the Playwright arguments `['--no-sandbox', '--disable-setuid-sandbox', ...]` as they are required for GitHub Actions compatibility.

### **B. LLM Generator Agent (`llm_generator.py`)**
- **Responsibility:** Generates the initial batch of ideas based on various strategies (e.g., Keyword Combination, Winner Perspective).
- **Key Skill:** Manages multiple LLM Providers (`Gemini`, `Groq`, `GitHub AI`).
- **Rule:** When modifying the generation phase, ensure you preserve the diversity constraint. For instance, Groq should instantiate both `openai/gpt-oss-120b` and `llama-3.3-70b-versatile`.

### **C. Evaluator Agent (`evaluator.py`)**
- **Responsibility:** Cross-evaluates the generated submissions using multiple LLMs (Groq, Gemini, GitHub) to ensure objective scoring.
- **Key Skill:** Multi-Agent consensus scoring and Self-Critique generation.
- **Rule:** Always enforce `use_multi_agent=True` during critical evaluations. Respect the rate limits (`asyncio.sleep()`) added for each provider to avoid 429 errors.

### **D. Self-Learning Engine (`self_learning.py`)**
- **Responsibility:** Analyzes top-scoring submissions, extracts winning patterns, and dynamically generates an improved prompt for the next iteration.
- **Key Skill:** Recursive refinement and pattern extraction.
- **Rule:** Keep iterations low (e.g., `max_iterations=2`) to fit within API rate limits and action timeouts.

### **E. Refiner & Tournament Agent (`refiner.py`)**
- **Responsibility:** Removes duplicates, ensures strategy diversity, runs 1:1 head-to-head tournaments, and applies final polishes.
- **Key Skill:** The `final_polish` component MUST generate a compelling, copy-paste-ready `작명 배경 및 의미` (Naming Reason) intended directly for the contest submission form, along with internal `[폴리싱됨] 심사위원 노트`.
- **Rule:** Ensure the model used for `final_polish` and `refine_top_submissions` is `llama-3.3-70b-versatile` for superior instruction-following.

### **F. Notifier Agents (`notion_saver.py`, `slack_notifier.py`)**
- **Responsibility:** Save structured results to Notion and alert via Slack.
- **Key Skill:** Block Kit formatting (Slack) and Block mapping (Notion).
- **Rule:** Keep messages concise but informative. Include the explicit submission method tags (generated in `scraper.py`) in the Slack webhook block.

## 2. General Agent Workflow Guidelines

When an AI Agent is asked to modify or add features to this repository, it MUST:

1. **Check Dependencies First:** Always identify which sub-agent is responsible. For instance, if the request is about "saving new fields," modify `state.py` first, then update the scraper, then the Notion saver.
2. **Respect the Schema (`state.py`):** The `Submission` and `ContestInfo` TypedDicts are the single source of truth for moving data between agents. If you need a new property, add it to `state.py` first.
3. **Handle Rate Limits (Crucial):** All external API calls (Groq, Gemini, GitHub) must have `try/except` blocks handling exceptions without crashing the pipeline, and MUST include `asyncio.sleep()` where appropriate to prevent 429 Too Many Requests errors.
4. **Preserve Agent Autonomy:** Do not merge classes into monolithic blocks. The pipeline is designed to be a LangGraph-like directed sequence (`Scrape` → `Generate` → `Evaluate` → `Learn` → `Refine` → `Notify`).
5. **JSON Extraction Safety:** Always use regex `re.search(r'```json\s*([\s\S]*?)\s*```')` followed by a fallback to `json.loads(response.strip())` to prevent JSON parsing errors from rogue markdown text.

## 3. How to Use this Harness
- **If adding a new strategy:** Add it to `CREATIVE_STRATEGIES` in `llm_generator.py`.
- **If changing the evaluation criteria:** Update `generate_evaluation_criteria` in `evaluator.py`.
- **If changing output format for users:** Update `final_polish` in `refiner.py`.
- **If adding a new LLM provider:** Abstract it under the `LLMClient` base class in `llm_generator.py` and register it in `create_llm_clients()`.
