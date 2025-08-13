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

## 2. POST /evaluate
- TODO

## Frontend
- techstack: html/css/vanilla js
- 생성된 결과값 (result0003.json)의 내용을 분석해 보여주는 용도. 
- GET /result/3 을 호출하면 frontend 하위에 만들어진 html 페이지를 가져오고, result0003.json의 데이터를 가져와 보여줌. 