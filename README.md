# Shorts Assistant

제품 추천용 유튜브 쇼츠/틱톡 제작 파일을 한 번에 만드는 개인용 로컬 자동화 도구입니다. 제품 정보와 이미지/영상 소스, 인포크 같은 프로필 링크를 넣으면 대본, Typecast 입력 문장, Edge TTS 테스트 음성, CapCut 자막, SRT, BGM 복사, 이미지 생성 프롬프트, 업로드 문구, 인포크 연결 가이드, Notion 카테고리 페이지 템플릿, CapCut 패키지 폴더를 생성합니다.

## 설치

Python 3.10 이상을 권장합니다.

```powershell
cd C:\Users\senna\OneDrive\Documents\Playground\shorts-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Playwright를 실제 Typecast 웹 자동화에 사용할 계획이라면 나중에 아래 명령도 실행하세요.

```powershell
playwright install
```

## 실행

```powershell
streamlit run app.py
```

브라우저가 열리면 제품명, 카테고리, 가격대, 타겟 사용자, 장점 3개, 주의점, 인포크/프로필 링크를 입력하고 `쇼츠 패키지 생성`을 누릅니다.

앱은 세 개의 탭으로 구성됩니다.

- **패키지 생성**: 기존 생성 화면
- **히스토리**: `outputs/`에 쌓인 과거 프로젝트를 골라 대본/자막/업로드 문구를 다시 보고 다운로드
- **제품 관리**: `data/products.json`에 자동 저장된 제품 목록을 표에서 수정/삭제하고 CSV로 다운로드

사이드바에서 TTS 음성/속도와 기본 인포크 링크를 입력한 뒤 `설정 저장`을 누르면 `data/settings.json`에 저장되어 다음 실행부터 자동으로 채워집니다.

아직 유료 제휴나 파트너스 활동을 하지 않는 단계라면 `유료 제휴/파트너스 고지 문구 포함` 옵션은 꺼두세요. 나중에 실제 제휴 링크를 쓰기 시작하면 이 옵션을 켜서 업로드 문구에 고지를 포함할 수 있습니다.

## 파이프라인 서버 + 이미지 생성 (GPT · Higgsfield)

```powershell
python pipeline_server.py        # http://localhost:8787
```

- `/` — 6단계 쇼츠 파이프라인 (n8n 스타일 캔버스)
- `/image` — **사진/그림 생성** (Higgsfield Soul text-to-image). 프롬프트·비율·장수를 넣으면 이미지가 `outputs/pipeline_runs/_uploads/`에 저장되고, "쇼츠 만들기 →"로 그 이미지를 제품 이미지로 바로 넘길 수 있다. `.env`의 `HIGGSFIELD_API_KEY/SECRET` 필요, 장당 크레딧 소모. 모델은 `HIGGSFIELD_IMAGE_MODEL`로 교체 가능(기본 `higgsfield-ai/soul/standard`). **사진 첨부(최대 8장)** 하면 그 사진을 참고/수정/합성한다 — 이때 모델은 `HIGGSFIELD_EDIT_MODEL`(기본 `higgsfield-ai/popcorn/auto`, 출력 720p). 결과 카드의 "이어서 편집"으로 결과물을 다시 첨부해 계속 고칠 수 있다.

  **엔진 선택 — GPT / Higgsfield (둘 다 선택 가능).** 화면 위 엔진 버튼으로 고른다. 둘 다 켜면 같은 프롬프트로 나란히 돌려 결과를 한 화면에서 비교하고(카드마다 엔진 배지), 한쪽만 실패해도 성공한 쪽은 그대로 나온다.
  - **GPT** — OpenAI Images API(`gpt-image-2`, `OPENAI_IMAGE_MODEL`로 교체 가능). `.env`의 `OPENAI_API_KEY`만 있으면 되고 **API 크레딧**에서 차감된다(ChatGPT 구독 쿼터 아님). 첨부 없으면 `/v1/images/generations`, 첨부가 있으면 `/v1/images/edits`로 간다. 폭·높이가 16의 배수여야 해서 비율→크기는 `SIZE_BY_ASPECT`로 고정 매핑(9:16 → 1024x1824).
  - **참고 이미지 순서** — 두 엔진 모두 첨부가 2장 이상이면 프롬프트 앞에 `first image = …, second image = …` 라벨이 자동으로 붙어 "첫 번째 사진의 인물을 두 번째 사진 배경에"처럼 번호로 지목할 수 있다. UI 썸네일에도 ①②③ 번호가 표시된다.

## 서버 배포 (Streamlit Community Cloud)

폰이나 다른 PC에서 쓰고 싶으면 무료로 배포할 수 있습니다.

1. 이 폴더를 GitHub **비공개 저장소**로 올립니다.
2. https://share.streamlit.io 에서 GitHub 계정으로 로그인 후 `New app` → 저장소 선택, Main file은 `app.py`.
3. 앱 설정의 **Secrets**에 아래를 넣습니다.

```toml
APP_PASSWORD = "원하는_비밀번호"
ANTHROPIC_API_KEY = "sk-ant-..."
```

`APP_PASSWORD`를 넣으면 접속 시 비밀번호를 요구합니다(로컬에서는 설정하지 않으면 그대로 통과). 배포 시 `requirements.txt`의 "로컬 전용" 블록은 지워도 됩니다.

서버 배포 시 알아둘 점:

- 서버 저장소는 재시작 때 초기화되므로 결과는 `파일 다운로드` 탭의 **전체 결과 zip 다운로드**로 바로 받으세요. 제품 DB(products.json)도 휘발성이니 중요하면 제품 관리 탭에서 CSV로 백업.
- moviepy 렌더링은 무료 서버에서 느릴 수 있습니다(짧은 영상 기준 1~3분).
- 같은 와이파이 안에서만 쓸 거면 배포 없이 `streamlit run app.py --server.address 0.0.0.0`으로 실행하고 폰에서 `http://PC내부IP:8501`로 접속하면 됩니다.

## 인포크 연결 방식

추천 구조는 아래처럼 운영합니다.

```text
쇼츠/틱톡 영상
  -> 인포크 메인 링크
    -> 카테고리 버튼
      -> Notion 또는 공개 페이지의 제품 목록
```

예를 들어 인포크 메인에는 아래처럼 버튼을 둡니다.

- 사무실템
- 자취템
- 주방템
- 생활템

각 버튼은 Notion 카테고리 페이지 공유 링크로 연결합니다. 앱에서 `현재 카테고리 페이지 링크`를 입력하면 업로드 문구와 대본 CTA가 `프로필 링크의 카테고리에서 확인` 형태로 생성됩니다.

`카테고리별 링크 목록`에는 아래 형식으로 저장할 수 있습니다.

```text
사무실템=https://notion.so/...
자취템=https://notion.so/...
주방템=https://notion.so/...
```

생성 결과에는 아래 파일이 추가됩니다.

- `inpock_link_guide.txt`: 인포크 버튼 연결 안내
- `notion_category_page.md`: Notion 페이지에 붙여넣을 제품 목록 템플릿

Notion 제품 카드에는 아래 정보를 넣을 수 있습니다.

- 제품명
- 카테고리
- 가격대
- 추천 대상
- 제품 링크
- 제품 이미지 URL
- 좋아 보이는 포인트 3개
- 주의점
- 옵션/사이즈 메모
- 배송/품절 메모
- 후기 메모
- 제품 상태
- 개인 메모
- 영상에서 쓸 문구

## Notion API 자동 추가

Notion API 토큰이 있으면 생성한 `notion_category_page.md` 내용을 Notion 페이지 끝에 자동으로 추가할 수 있습니다.

1. Notion 개발자 페이지에서 integration을 만듭니다.
2. integration에 콘텐츠 삽입 권한을 줍니다.
3. 제품 목록으로 쓸 Notion 페이지를 엽니다.
4. 페이지 오른쪽 위 `...` 메뉴에서 `Connections`에 해당 integration을 연결합니다.
5. `.env` 파일에 토큰을 넣거나, 앱 화면의 `Notion API 토큰` 입력칸에 붙여넣습니다.

```env
NOTION_API_KEY=secret_xxx
NOTION_TARGET_PAGE_ID=https://www.notion.so/...
```

앱에서 `생성 후 Notion 페이지에 자동 추가`를 켜면 됩니다. API 토큰이 있어도 페이지가 integration에 공유되어 있지 않으면 Notion API는 404를 반환할 수 있습니다.

## BGM 넣는 법

`assets/bgm` 폴더에 mp3, wav, m4a 파일을 넣어두세요. 파일명에 아래 키워드가 있으면 우선 선택됩니다.

- 빠른 리뷰형: `fast`, `upbeat`, `review`
- 감성 자취템형: `cozy`, `soft`, `daily`
- 직장인 현실 공감형: `calm`, `minimal`, `office`

BGM이 없어도 패키지 생성은 계속 진행됩니다.

## 초안 영상 자동 렌더링

`초안 영상 자동 렌더링 (mp4)` 옵션을 켜면 업로드한 제품 이미지 + Edge TTS 음성 + 자막을 합쳐 9:16 초안 영상(`draft_video.mp4`)을 만듭니다. CapCut 패키지의 `videos` 폴더에도 복사됩니다.

- 용도: 대본 길이/타이밍/구성 확인, 빠른 대량 업로드 테스트
- 한계: 이미지 슬라이드쇼 수준이므로 반응이 좋은 제품은 CapCut에서 다듬는 것을 추천
- 자막 폰트: `assets/fonts`에 한글 TTF를 넣으면 우선 사용, 없으면 Windows 맑은고딕 사용
- 실패해도 나머지 파일 생성은 계속 진행됩니다 (moviepy/ffmpeg 문제 시 경고만 표시)

## 이미지/영상 업로드

Streamlit 화면에서 제품 이미지와 영상 소스를 업로드하면 출력 폴더의 `source_product_images`, `source_videos`에 저장되고, `capcut_package/images`, `capcut_package/videos`에도 복사됩니다. 저작권 리스크를 줄이기 위해 기본 워크플로우는 직접 준비한 소스 기반입니다.

## Edge TTS

Edge TTS는 테스트용 음성입니다. 생성 파일은 `edge_tts_test.mp3`입니다. 네트워크나 edge-tts 환경 문제로 실패해도 대본, 자막, 업로드 문구, CapCut 패키지는 계속 생성됩니다.

기본 음성은 `.env.example`의 `DEFAULT_TTS_VOICE=ko-KR-SunHiNeural`을 참고하세요. 실제 설정은 `.env` 파일을 만들어 관리하면 됩니다.

## Typecast 최종 음성으로 교체

1. 출력 폴더의 `typecast_lines.txt`를 엽니다.
2. Typecast에 한 줄씩 붙여넣어 최종 음성을 생성합니다.
3. 다운로드한 음성 파일을 CapCut에서 `edge_tts_test.mp3` 대신 사용합니다.

나중에 `modules/macro/typecast_macro.py`의 dry-run 구조를 실제 Playwright 또는 PyAutoGUI 자동화로 확장할 수 있습니다.

## CapCut 패키지 사용법

출력 폴더 안에 아래 구조가 생성됩니다.

```text
outputs/
  제품명_YYYYMMDD_HHMM/
    script.txt
    typecast_lines.txt
    typecast_lines_numbered.txt
    edge_tts_test.mp3
    capcut_subtitles.txt
    subtitles.srt
    selected_bgm.mp3
    edit_guide.txt
    upload_info.txt
    image_prompts.txt
    tiktok_references.txt
    product_info.json
    capcut_package/
      videos/
      images/
      audio/
      subtitles/
      guide/
```

CapCut에서는 `capcut_package` 폴더 안의 파일을 가져오면 됩니다. `audio`에는 테스트 음성과 BGM, `subtitles`에는 SRT와 자막 txt, `guide`에는 편집 가이드와 업로드 문구가 들어갑니다.

## 매크로 모듈

`modules/macro/typecast_macro.py`와 `modules/macro/capcut_macro.py`는 지금은 안전한 dry-run 모드가 기본입니다. 실제 클릭이나 입력을 하기 전에 어떤 순서로 동작할지 로그만 출력합니다.

설정은 `modules/macro/macro_config.py`에서 관리합니다.

- CapCut 실행 경로
- Typecast URL
- 버튼 좌표
- 단축키
- 대기 시간
- dry-run 여부

## Claude API 대본 생성

기본은 API 키 없이 동작하는 템플릿 대본입니다. 더 자연스러운 대본을 원하면 Claude API를 연결할 수 있습니다.

1. `.env`에 `ANTHROPIC_API_KEY=sk-ant-...`를 넣습니다. (또는 사이드바에 직접 입력)
2. 사이드바의 `Claude API로 대본 생성`을 켭니다.
3. API 호출이 실패하면 자동으로 템플릿 대본으로 대체되고 경고가 표시됩니다.

모델은 기본 `claude-sonnet-4-5`이며 `.env`의 `ANTHROPIC_MODEL`로 바꿀 수 있습니다. 구현은 `modules/llm_script_generator.py`에 있습니다.

`.env.example`:

```env
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-5
USE_LLM=false
DEFAULT_TTS_VOICE=ko-KR-SunHiNeural
```

## 자주 발생하는 오류

### Edge TTS 생성 실패

인터넷 연결, edge-tts 패키지, 음성 이름을 확인하세요. 실패해도 나머지 파일은 생성됩니다.

### SRT 길이가 실제 음성과 다름

mp3 길이를 읽을 수 있으면 실제 길이에 맞추고, 실패하면 목표 영상 길이 기준으로 임시 분배합니다. 최종 Typecast 음성으로 교체한 뒤 CapCut에서 자막 타이밍을 미세 조정하세요.

### BGM이 선택되지 않음

`assets/bgm`에 mp3, wav, m4a 파일이 있는지 확인하세요.

### pyautogui 설치 오류

매크로를 바로 쓰지 않는다면 앱 실행에는 필수 흐름이 아닙니다. 다만 requirements 설치 중 문제가 생기면 Python 버전과 Windows 빌드 환경을 확인하세요.
