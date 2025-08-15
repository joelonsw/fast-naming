# Fast Naming
이 프로젝트는 슬로건/네이밍 공모전에 출품할 가장 우수한 작명을 할 수 있도록, LLM의 역량을 총 동원하여 후보작을 생성하고 이를 자체적으로 평가하도록 합니다. 
가장 우수한 작명을 해낼 수 있도록, 다음과 같은 절차를 따릅니다. 

## 1. POST /name
### 1. 공모전 내용을 사용자로부터 받기
- 다음과 같이 사용자로 부터 공모전에 대한 내용을 입력받습니다. 
```
POST /name
{
    # essential
    "contestTitle": "공모전명",
    "contestContent": "공모전 내용",
    "contestHeldBy": "주최기관",
    "contestType": "슬로건" | "네이밍",
    "contestHeldByType": "공공기관" | "사기업" | "학교",

    # optional
    "contestCriteria": {
        "배점기준1": 10,
        "배점기준2": 20,
        "배점기준3": 30,
        "배점기준4": 40,
    }
}
```

### 2. 입력된 공모전 분석 후 미리 정의되어 있는 모범 사례 중에서 few shot으로 사용할 예시 추출
- examples/examples.json 에는 모범사례가 있습니다. 
- 사용자의 input의 contestType, contestHeldByType과 동일한 값을 가진 json 객체를 example.json에서 찾으세요. 
- 해당 데이터는 3번의 prompt에서 few shot으로 사용될 예정입니다. successfulExamples라는 변수에 저장하세요. 
- 예시 데이터는 다음과 같습니다. 
```json
{
    "contestType":"네이밍",
    "contestHeldByType":"사기업",
    "contestTitle":"여기어때 전용서체 네이밍 공모전",
    "contestWinner":"잘난체",
    "strength":"창의성, 위트"
}
```

### 3. few shot 기반의 prompt 작성, temperature와 모델을 변경하며 다양한 공모전 입후보작 생성
- system prompt
```
당신은 대한민국 최고의 네이미스트 입니다. 당신은 주최측이 원하는 네이밍을 무조건 제공하는 네이미스트입니다. 
다음 공모전에 출품할 주최측이 원하는 이름을 만드세요.
```
- user prompt : 매번 호출할 때 마다, 2번에서 할당한 successfulExamples에서 3가지 예시를 추출해 첨부하세요. 
```
{{userInput.contestTitle}} 공모전에 참여하여 수상 확률이 가장 높은 3가지 슬로건을 만드세요:
<contest_description>
{{userInput.contestContent}}
</contest_description>

앞서 비슷한 유형의 공모전에서 수상한 작품들을 참고하세요. 
<sample_input1>
{{exampleJson.contestTitle}}
</sample_input1>
<ideal_output1>
{{exampleJson.contestWinner}}
</ideal_output1>
<strength1>
{{exampleJson.strength}}
</strength1>

<sample_input2>
{{exampleJson.contestTitle}}
</sample_input2>
<ideal_output2>
{{exampleJson.contestWinner}}
</ideal_output2>
<strength2>
{{exampleJson.strength}}
</strength2>

<sample_input3>
{{exampleJson.contestTitle}}
</sample_input3>
<ideal_output3>
{{exampleJson.contestWinner}}
</ideal_output3>
<strength3>
{{exampleJson.strength}}
</strength3>

guidelines:
1. {{userInput.contestContent}}에 있는 요구사항을 모두 준수해야 합니다. 
2. {{userInput.contestHeldBy}}에서 좋아할 작명이여야 합니다. 
```
- 모든 답변은 다음과 같은 json 형식으로 생성되어야 합니다. 한 번의 LLM 질문에 3가지 출품작을 생성하도록 해야합니다. 
```json
[
    {
        "submission": "공모전 출품작 이름1",
        "description": "해당 공모전 출품작을 생성하게 된 이유1"
    },
    {
        "submission": "공모전 출품작 이름2",
        "description": "해당 공모전 출품작을 생성하게 된 이유2"
    },    
    {
        "submission": "공모전 출품작 이름3",
        "description": "해당 공모전 출품작을 생성하게 된 이유3"
    }
]
```
- LLM의 활용 원칙
    - 모델의 temperature, top_p를 변경하면서, 각 모델별로 5번의 LLM 호출이 필요합니다. 
    - LLM이 생성해낸 모든 출품작은 json으로 모두 취합해 해당 프로젝트 폴더의 result 디렉토리 안, result0001.json 형식으로 저장하세요.
    - Github AI, Groq, Google LLM과 통신할 수 있도록 모듈을 만드세요. 
- https://github.com/marketplace/models/azure-openai/gpt-5/playground
    - 사용할 모델
        - openai/gpt-5
        - microsoft/Phi-4
        - deepseek/DeepSeek-R1-0528
    - 예시 연동 코드
        ```python
        import os
        from azure.ai.inference import ChatCompletionsClient
        from azure.ai.inference.models import SystemMessage, UserMessage
        from azure.core.credentials import AzureKeyCredential

        endpoint = "https://models.github.ai/inference"
        model = "openai/gpt-5"
        token = os.environ["GITHUB_TOKEN"]

        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
        )

        response = client.complete(
            messages=[
                SystemMessage("You are a helpful assistant."),
                UserMessage("What is the capital of France?"),
            ],
            model=model
        )

        print(response.choices[0].message.content)
        ```
- https://console.groq.com/keys
    - 사용할 모델
        - openai/gpt-oss-120b
        - deepseek-r1-distill-llama-70b
        - llama-3.3-70b-versatile
    - 예시 연동 코드
        ```python
        from groq import Groq

        client = Groq()
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
            {
                "role": "user",
                "content": ""
            }
            ],
            temperature=1,
            max_completion_tokens=8192,
            top_p=1,
            reasoning_effort="medium",
            stream=True,
            stop=None
        )

        for chunk in completion:
            print(chunk.choices[0].delta.content or "", end="")
        ```
- https://aistudio.google.com/prompts/new_chat
    - 사용할 모델
        - gemini-2.5-flash
    - 예시 연동 코드
        ```python
        from google import genai

        # The client gets the API key from the environment variable `GEMINI_API_KEY`.
        client = genai.Client()

        response = client.models.generate_content(
            model="gemini-2.5-flash", contents="Explain how AI works in a few words"
        )
        print(response.text)
        ```

- https://api.together.ai/models/lgai/exaone-3-5-32b-instruct
    - 사용할 모델
        - lgai/exaone-deep-32b
        - lgai/exaone-3-5-32b-instruct
    - 예시 연동 코드
        ```python
        from together import Together

        client = Together()

        response = client.chat.completions.create(
            model="lgai/exaone-3-5-32b-instruct",
            messages=[
            {
                "role": "user",
                "content": "What are some fun things to do in New York?"
            }
            ]
        )
        print(response.choices[0].message.content)
        ```

## 2. POST /evaluate
### 1. 결과 페이지에서 해당 API 호출
- 사용자가 특정 결과 페이지에서 평가하기 버튼을 눌렀을 때 호출됩니다. 
- 해당 엔드포인트는 특정 결과 (resultxxxx.json) 에서 생성된 답변 submissions에 대해 채점한 결과를 제공해야 합니다. 

### 2. 생성된 submissions에 대해 채점 기준 마련하기
- 앞서 호출된 POST /name의 contestCriteria가 있었다면, 이를 사용하세요.
- 없다면 LLM을 호출하여 채점 기준을 마련하세요. 
- groq의 openai/gpt-oss-120b 모델을 사용하세요. 
- user prompt
```
당신은 {{userInput.contentTitle}}의 심사위원입니다. 
{{userInput.contestContent}} 를 참고하여, 공모전의 공정한 평가기준을 마련하세요.
평가 기준은 4가지로 마련하며, 각 평가기준의 총합은 100이 되어야 합니다. 
다음과 같이 json으로 생성하여 반환하세요. 

"contestCriteria": {
    "배점기준1": 10,
    "배점기준2": 20,
    "배점기준3": 30,
    "배점기준4": 40,
}
```

### 3. 실제 생성된 submissions에 대해 채점하기
- 위의 2번에서 확정한 채점기준을 바탕으로, 공정하게 채점을 진행하세요. 결과값은 submissions 객체에 score를 추가해야 합니다. 배점기준 별로 점수를 기록하세요. 
- 예시
```json
{
    "submission": "디지털 혁신과 투명한 소통으로 지속가능한 지역상생을 실현한다.",
    "description": "‘디지털’과 ‘투명’이라는 키워드로 현대적 변화를 강조하고, ‘지속가능’·‘지역상생’을 결합해 GBDC가 지역과 함께 성장한다는 메시지를 명확히 전달한다.",
    "provider": "groq",
    "model": "openai/gpt-oss-120b",
    "temperature": 0.7,
    "top_p": 0.95,
    "iteration": 1,
    "score": {
        "배점기준1": 10,
        "배점기준2": 20,
        "배점기준3": 30,
        "배점기준4": 40,
    }
},
```
- https://aistudio.google.com/prompts/new_chat
    - 사용할 모델 : gemini-2.5-pro
- system prompt
```
당신은 {{userInput.contentTitle}}의 심사위원입니다. 
{{userInput.contestContent}} 를 참고하여, 공모전의 공정한 평가기준을 마련하세요.
평가 기준은 4가지입니다.
"contestCriteria": {
    "배점기준1": 10,
    "배점기준2": 20,
    "배점기준3": 30,
    "배점기준4": 40,
}
```
- user prompt
```
다음 {{userInput.contentTitle}}에 출품한 작품들에 대해 평가를 진행하세요. 

<submissions>
  "submissions": [
    {
      "submission": "디지털 혁신과 투명한 소통으로 지속가능한 지역상생을 실현한다.",
      "description": "‘디지털’과 ‘투명’이라는 키워드로 현대적 변화를 강조하고, ‘지속가능’·‘지역상생’을 결합해 GBDC가 지역과 함께 성장한다는 메시지를 명확히 전달한다.",
      "provider": "groq",
      "model": "openai/gpt-oss-120b",
      "temperature": 0.7,
      "top_p": 0.95,
      "iteration": 1
    },
    {
      "submission": "협력과 공유로 체감하는 변화를 실용적으로 구현한다.",
      "description": "‘협력’·‘공유’·‘체감’·‘변화’·‘실용’이라는 다섯 키워드를 조합해, GBDC가 공동체와 함께 직접 체감할 수 있는 실용적 변화를 주도한다는 점을 강조한다.",
      "provider": "groq",
      "model": "openai/gpt-oss-120b",
      "temperature": 0.7,
      "top_p": 0.95,
      "iteration": 1
    },
    // ...
  ]
</submissions>
```
- 채점된 결과는 가장 높은 점수를 가진 submission을 첫번째로 하여 순서대로 정렬하여, result 디렉토리 안, score0001.json 형식으로 저장하세요. 

## API Endpoints

### GET /
- **홈페이지**: 공모전 정보 입력 폼 제공
- **기능**: 
  - 공모전 정보 입력 (제목, 내용, 주최기관, 유형 등)
  - POST /name API 호출
  - 결과 확인 및 결과 페이지로 이동
  - 예시 데이터로 폼 자동 채우기

### GET /result/{number}
- **결과 페이지**: 생성된 작명 결과를 시각적으로 표시
- **기능**:
  - 공모전 정보 표시
  - 통계 대시보드 (총 작명 수, 모델별 분포 등)
  - 작명 목록 필터링 및 검색
  - 참고된 예시 데이터 표시

### GET /api/result/{number}
- **결과 데이터 API**: JSON 형태로 결과 데이터 제공

### POST /evaluate
- **평가 API**: 생성된 작명에 대한 AI 기반 평가 및 채점
- **입력**: result_number (평가할 결과 파일 번호)
- **출력**: 평가된 submissions (점수 포함) 및 score 파일

### GET /api/score/{number}
- **평가 결과 데이터 API**: JSON 형태로 평가 결과 데이터 제공

## Frontend
- **기술 스택**: HTML/CSS/Vanilla JavaScript
- **파일 구조**:
  ```
  frontend/
  ├── home.html      # 홈페이지 (GET /)
  ├── home.css       # 홈페이지 스타일
  ├── home.js        # 홈페이지 로직
  ├── result.html    # 결과 페이지 (GET /result/{number})
  ├── styles.css     # 결과 페이지 스타일
  └── script.js      # 결과 페이지 로직
  ```
- **주요 기능**:
  - 반응형 디자인 (모바일/데스크톱 최적화)
  - 실시간 폼 검증
  - 로딩 상태 표시
  - 오류 처리 및 사용자 피드백
  - 예시 데이터 자동 채우기
  - 결과 필터링 및 검색 