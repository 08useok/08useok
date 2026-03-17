# AGENTS.md
# Keep this file under 60 lines. Operational info only — no status updates.

## Build & Run
```bash
# 의존성 설치
/c/Users/useok/AppData/Local/Python/pythoncore-3.14-64/python.exe -m pip install flask zai-sdk requests

# 서버 실행
/c/Users/useok/AppData/Local/Python/pythoncore-3.14-64/python.exe app.py
# → http://localhost:5000
```

## Validation
- Run server: `python app.py` (Flask dev server)
- Syntax check: `python -m py_compile app.py`
- Tests: `python -m pytest test_app.py -v` (37 tests, mocked ZAI client)

## Operational Notes
- Python 경로: `C:\Users\useok\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- ZAI API key: `cogvideox_text.py` 참고 (하드코딩)
- 영상 저장 위치: `videos/` (자동 생성)
- SSE 엔드포인트: `POST /generate` — 1초마다 progress 이벤트 전송
- 영상 서빙: `GET /videos/<filename>`

## Codebase Patterns
- `_get_attr_or_key(obj, key)`: dict/object 모두 처리하는 ZAI 응답 파싱 헬퍼
- 파일명 규칙: `N_video.mp4` (videos/ 내 기존 파일 수 + 1)
- `warnings.filterwarnings("ignore")` 최상단 필수 (Pydantic V1 경고 억제)
