# IMPLEMENTATION_PLAN

## Status: Complete

All functionality implemented. `app.py` (Flask backend) and `templates/index.html` (chat UI) are ready.

---

## Priority 1 — Flask Backend (`app.py`) ✓

- [x] **Flask app skeleton** — `app.py` with routes, ZAI client, helpers
- [x] **`POST /generate` SSE endpoint** — prompt validation, SSE progress/done/error events, video download
- [x] **`GET /videos/<filename>` route** — `send_from_directory()`

## Priority 2 — Chat UI (Single Page) ✓

- [x] **`templates/index.html`** — full chat layout, CSS bubbles, JS interaction
  - User bubble (right, blue), assistant bubble (left, grey)
  - Progress bar + elapsed time, video player + download link
  - Enter to send, Shift+Enter newline, empty prompt prevention
  - Input disabled during generation, auto-scroll

## Priority 3 — Polish & Validation

- [ ] **End-to-end manual test** — requires running server with real ZAI API

---

## Acceptance Criteria Checklist (from specs)

### video-generation.md
- [x] 빈 프롬프트 → 400 에러
- [x] 1초마다 SSE progress 이벤트
- [x] 완료 시 SSE done + filename
- [x] API 오류 시 SSE error 이벤트
- [x] `videos/` 자동 생성
- [x] `/videos/<filename>` 접근 가능

### chat-ui.md
- [x] 전송 시 사용자 말풍선 즉시 표시
- [x] 진행 바 + 경과 시간 1초마다 업데이트
- [x] 완료 시 영상 플레이어로 교체
- [x] 영상 바로 재생 가능 (autoplay + controls)
- [x] 다운로드 링크 동작 (download attribute)
- [x] 생성 중 입력 비활성화, 완료 후 재활성화
- [x] 빈 프롬프트 전송 불가
- [x] 새 메시지 시 자동 스크롤
