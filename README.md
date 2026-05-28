# Shorts Assistant

쿠팡 파트너스 제품 추천용 유튜브 쇼츠/틱톡 제작 파일을 한 번에 만드는 개인용 로컬 자동화 도구입니다. 제품 정보와 이미지/영상 소스를 넣으면 대본, Typecast 입력 문장, Edge TTS 테스트 음성, CapCut 자막, SRT, BGM 복사, 이미지 생성 프롬프트, 업로드 문구, CapCut 패키지 폴더를 생성합니다.

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

브라우저가 열리면 제품명, 카테고리, 가격대, 타겟 사용자, 장점 3개, 주의점, 쿠팡 파트너스 링크를 입력하고 `쇼츠 패키지 생성`을 누릅니다.

## BGM 넣는 법

`assets/bgm` 폴더에 mp3, wav, m4a 파일을 넣어두세요. 파일명에 아래 키워드가 있으면 우선 선택됩니다.

- 빠른 리뷰형: `fast`, `upbeat`, `review`
- 감성 자취템형: `cozy`, `soft`, `daily`
- 직장인 현실 공감형: `calm`, `minimal`, `office`

BGM이 없어도 패키지 생성은 계속 진행됩니다.

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

## LLM API 확장

초기 버전은 API 키 없이 템플릿 기반으로 실행됩니다. 나중에 OpenAI API나 Claude API를 붙일 때는 `modules/script_generator.py`의 `generate_script(product_info)` 구조를 유지한 채 내부 구현만 교체하면 됩니다.

`.env.example`:

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
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
