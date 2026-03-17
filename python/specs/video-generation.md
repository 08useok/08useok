# Video Generation

## 역할
채팅 UI에서 프롬프트를 받아 ZAI API로 영상을 생성하고, 진행 상태를 실시간으로 전달하는 백엔드 로직.

## API 엔드포인트

### POST /generate
- **요청**: `{ "prompt": "프롬프트 텍스트" }`
- **응답**: SSE(Server-Sent Events) 스트림

SSE 이벤트 형식:
```
data: {"type": "progress", "elapsed": 37, "percent": 45}
data: {"type": "progress", "elapsed": 242, "percent": 100}   ← 완료 직전 전송
data: {"type": "done", "filename": "3_video.mp4"}
data: {"type": "error", "message": "오류 내용"}
```
> 완료 시 `percent: 100` progress 이벤트를 먼저 보내 프로그레스 바를 100%로 채운 후 done 이벤트를 전송한다.

### GET /videos/<filename>
- `videos/` 디렉토리의 영상 파일을 스트리밍 서빙
- 다운로드 링크에도 동일하게 사용

## 영상 생성 로직
- 기존 `cogvideox_text.py`의 로직을 Flask 라우트에서 재사용
- 모델: `cogvideox-3`, quality: `quality`, size: `1920x1080`, fps: `60`, with_audio: `False`
- 파일명: `videos/` 내 `*_video.mp4` 개수 + 1 → `N_video.mp4`
- 생성 완료 후 `videos/` 에 저장, SSE로 `done` 이벤트 전송

## 진행률 계산
- CogVideoX-3 평균 생성 시간: 약 3~5분
- `percent = min(elapsed / 240 * 100, 95)` (완료 전 최대 95%)
- 완료 시 `percent: 100`

## Acceptance Criteria
- [ ] 프롬프트가 빈 문자열이면 400 에러 반환
- [ ] 영상 생성 중 1초마다 SSE progress 이벤트 전송
- [ ] 생성 완료 시 SSE done 이벤트에 filename 포함
- [ ] API 오류 발생 시 SSE error 이벤트 전송
- [ ] `videos/` 디렉토리 없으면 자동 생성
- [ ] `/videos/<filename>` 으로 생성된 파일 접근 가능
