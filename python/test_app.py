"""Tests for video generation Flask app.

Why: Verifies all acceptance criteria from specs/video-generation.md and
specs/chat-ui.md that can be tested without a real ZAI API key.
"""
import warnings
warnings.filterwarnings("ignore")

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from app import app, VIDEOS_DIR


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --- video-generation.md acceptance criteria ---


def test_empty_prompt_returns_400(client):
    """AC: 프롬프트가 빈 문자열이면 400 에러 반환"""
    resp = client.post("/generate", json={"prompt": ""})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_missing_prompt_returns_400(client):
    """AC: 프롬프트가 없으면 400"""
    resp = client.post("/generate", json={})
    assert resp.status_code == 400


def test_whitespace_only_prompt_returns_400(client):
    """AC: 공백만 있는 프롬프트도 빈 문자열 취급"""
    resp = client.post("/generate", json={"prompt": "   "})
    assert resp.status_code == 400


def test_videos_directory_exists():
    """AC: videos/ 디렉토리 없으면 자동 생성"""
    assert os.path.isdir(VIDEOS_DIR)


def test_serve_video_route(client):
    """AC: /videos/<filename> 으로 생성된 파일 접근 가능"""
    test_file = os.path.join(VIDEOS_DIR, "test_serve.mp4")
    with open(test_file, "wb") as f:
        f.write(b"\x00" * 100)
    resp = client.get("/videos/test_serve.mp4")
    assert resp.status_code == 200
    data = resp.data  # read fully so file handle is released
    resp.close()
    assert len(data) == 100
    os.remove(test_file)


def test_serve_video_missing_returns_404(client):
    resp = client.get("/videos/nonexistent_file.mp4")
    assert resp.status_code == 404


def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"AI Video Generator" in resp.data


def test_generate_returns_sse_content_type(client):
    """AC: 영상 생성 중 SSE 스트림 반환"""
    with patch("app.client") as mock_zai:
        mock_zai.videos.generations.return_value = {"id": "test-123"}
        mock_zai.videos.retrieve_videos_result.return_value = {
            "task_status": "FAIL",
        }
        resp = client.post("/generate", json={"prompt": "test prompt"})
        assert resp.content_type.startswith("text/event-stream")


def _parse_sse_events(data_bytes):
    """Parse SSE events from response data."""
    events = []
    for line in data_bytes.decode("utf-8").split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def test_generate_progress_then_done(client):
    """AC: 1초마다 SSE progress 이벤트 전송, 완료 시 done 이벤트에 filename 포함"""
    call_count = 0

    def mock_retrieve(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return {"task_status": "PROCESSING"}
        return {
            "task_status": "SUCCESS",
            "video_result": [{"url": "http://fake.example.com/video.mp4"}],
        }

    with patch("app.client") as mock_zai, \
         patch("app.requests.get") as mock_get, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"id": "test-vid"}
        mock_zai.videos.retrieve_videos_result.side_effect = mock_retrieve

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.iter_content.return_value = [b"fake video data"]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        resp = client.post("/generate", json={"prompt": "a beautiful sunset"})
        events = _parse_sse_events(resp.data)

        progress_events = [e for e in events if e["type"] == "progress"]
        done_events = [e for e in events if e["type"] == "done"]

        assert len(progress_events) >= 2
        assert all("elapsed" in e and "percent" in e for e in progress_events)
        assert len(done_events) == 1
        assert "filename" in done_events[0]
        assert done_events[0]["filename"].endswith("_video.mp4")

        # cleanup generated test file
        test_file = os.path.join(VIDEOS_DIR, done_events[0]["filename"])
        if os.path.exists(test_file):
            os.remove(test_file)


def test_generate_error_event_on_failure(client):
    """AC: API 오류 발생 시 SSE error 이벤트 전송"""
    with patch("app.client") as mock_zai, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"id": "test-fail"}
        mock_zai.videos.retrieve_videos_result.return_value = {
            "task_status": "FAIL",
        }
        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1


def test_generate_error_on_exception(client):
    """AC: 예외 발생 시에도 SSE error 이벤트"""
    with patch("app.client") as mock_zai:
        mock_zai.videos.generations.side_effect = RuntimeError("API down")
        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "API down" in error_events[0]["message"]


def test_non_json_body_returns_400(client):
    """Non-JSON request body should return 400, not crash."""
    resp = client.post("/generate", data="not json", content_type="text/plain")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_video_id_fallback_to_request_id(client):
    """When API returns request_id instead of id, use it as video_id."""
    with patch("app.client") as mock_zai, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"request_id": "fallback-123"}
        mock_zai.videos.retrieve_videos_result.return_value = {
            "task_status": "FAIL",
        }
        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        error_events = [e for e in events if e["type"] == "error"]
        # Should get FAIL error, not "ID를 가져올 수 없습니다" error
        assert len(error_events) == 1
        assert "실패" in error_events[0]["message"]
        mock_zai.videos.retrieve_videos_result.assert_called_with(id="fallback-123")


def test_missing_video_id_returns_error(client):
    """When API returns neither id nor request_id, yield error event."""
    with patch("app.client") as mock_zai:
        mock_zai.videos.generations.return_value = {}
        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "ID" in error_events[0]["message"]


def test_empty_video_result_on_success(client):
    """When SUCCESS but video_result is empty, yield error event."""
    with patch("app.client") as mock_zai, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"id": "test-vid"}
        mock_zai.videos.retrieve_videos_result.return_value = {
            "task_status": "SUCCESS",
            "video_result": [],
        }
        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        error_events = [e for e in events if e["type"] == "error"]
        assert any("video_result" in e["message"] for e in error_events)


def test_missing_url_in_video_result(client):
    """When SUCCESS but video_result[0] has no url, yield error event."""
    with patch("app.client") as mock_zai, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"id": "test-vid"}
        mock_zai.videos.retrieve_videos_result.return_value = {
            "task_status": "SUCCESS",
            "video_result": [{"cover_image_url": "http://example.com/thumb.jpg"}],
        }
        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        error_events = [e for e in events if e["type"] == "error"]
        assert any("URL" in e["message"] for e in error_events)


def test_object_style_api_response(client):
    """_get_attr_or_key should handle object-style (attribute) responses."""
    with patch("app.client") as mock_zai, \
         patch("app.time.sleep"):
        # Use MagicMock with attributes instead of dict
        gen_response = MagicMock()
        gen_response.id = "obj-test-123"
        # Make sure dict check fails
        gen_response.__class__ = type("ApiResponse", (), {})
        mock_zai.videos.generations.return_value = gen_response

        result_obj = MagicMock()
        result_obj.task_status = "FAIL"
        result_obj.__class__ = type("ApiResult", (), {})
        mock_zai.videos.retrieve_videos_result.return_value = result_obj

        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "실패" in error_events[0]["message"]


def test_progress_percent_is_integer(client):
    """Percent in progress events must be an integer (not float)."""
    call_count = 0

    def mock_retrieve(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return {"task_status": "PROCESSING"}
        return {
            "task_status": "SUCCESS",
            "video_result": [{"url": "http://fake.example.com/video.mp4"}],
        }

    with patch("app.client") as mock_zai, \
         patch("app.requests.get") as mock_get, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"id": "test-vid"}
        mock_zai.videos.retrieve_videos_result.side_effect = mock_retrieve

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.iter_content.return_value = [b"fake"]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        progress_events = [e for e in events if e["type"] == "progress"]
        for e in progress_events:
            assert isinstance(e["percent"], int), f"percent should be int, got {type(e['percent'])}"

        # cleanup
        done_events = [e for e in events if e["type"] == "done"]
        if done_events:
            test_file = os.path.join(VIDEOS_DIR, done_events[0]["filename"])
            if os.path.exists(test_file):
                os.remove(test_file)


def test_sse_response_headers(client):
    """SSE response should include Cache-Control and X-Accel-Buffering headers."""
    with patch("app.client") as mock_zai, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"id": "test-123"}
        mock_zai.videos.retrieve_videos_result.return_value = {
            "task_status": "FAIL",
        }
        resp = client.post("/generate", json={"prompt": "test"})
        assert resp.headers.get("Cache-Control") == "no-cache"
        assert resp.headers.get("X-Accel-Buffering") == "no"


def test_download_failure_returns_error(client):
    """When video download fails, yield SSE error event."""
    with patch("app.client") as mock_zai, \
         patch("app.requests.get") as mock_get, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"id": "test-vid"}
        mock_zai.videos.retrieve_videos_result.return_value = {
            "task_status": "SUCCESS",
            "video_result": [{"url": "http://fake.example.com/video.mp4"}],
        }
        mock_get.side_effect = ConnectionError("download failed")

        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "download failed" in error_events[0]["message"]


def test_generation_parameters_match_spec(client):
    """Verify exact API parameters from specs/video-generation.md are sent.

    Why: A wrong model name or missing parameter silently produces bad results
    or API errors. This test catches parameter regressions at the source.
    """
    with patch("app.client") as mock_zai, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"id": "test-params"}
        mock_zai.videos.retrieve_videos_result.return_value = {
            "task_status": "FAIL",
        }
        client.post("/generate", json={"prompt": "test prompt"})

        mock_zai.videos.generations.assert_called_once_with(
            model="cogvideox-3",
            prompt="test prompt",
            quality="quality",
            with_audio=False,
            size="1920x1080",
            fps=60,
        )


def test_filename_numbering_with_existing_files(client):
    """Filename should be N+1 where N is the count of existing *_video.mp4 files.

    Why: The numbering logic counts only *_video.mp4 files. Without this test,
    a regression (e.g., counting all files) would silently produce wrong names.
    """
    # Create two pre-existing video files
    pre1 = os.path.join(VIDEOS_DIR, "1_video.mp4")
    pre2 = os.path.join(VIDEOS_DIR, "2_video.mp4")
    noise = os.path.join(VIDEOS_DIR, "other.txt")
    for f in (pre1, pre2, noise):
        open(f, "w").close()

    try:
        with patch("app.client") as mock_zai, \
             patch("app.requests.get") as mock_get, \
             patch("app.time.sleep"):
            mock_zai.videos.generations.return_value = {"id": "test-num"}
            mock_zai.videos.retrieve_videos_result.return_value = {
                "task_status": "SUCCESS",
                "video_result": [{"url": "http://fake.example.com/v.mp4"}],
            }
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.iter_content.return_value = [b"data"]
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            resp = client.post("/generate", json={"prompt": "test"})
            events = _parse_sse_events(resp.data)
            done = [e for e in events if e["type"] == "done"]
            assert len(done) == 1
            # 2 existing *_video.mp4 → next should be 3_video.mp4
            assert done[0]["filename"] == "3_video.mp4"
    finally:
        for f in (pre1, pre2, noise, os.path.join(VIDEOS_DIR, "3_video.mp4")):
            if os.path.exists(f):
                os.remove(f)


def test_download_http_error_returns_sse_error(client):
    """When the video CDN returns an HTTP error (e.g. 403), yield SSE error.

    Why: raise_for_status() throws HTTPError for non-2xx responses.
    This path is distinct from a ConnectionError and must also be caught.
    """
    from requests.exceptions import HTTPError

    with patch("app.client") as mock_zai, \
         patch("app.requests.get") as mock_get, \
         patch("app.time.sleep"):
        mock_zai.videos.generations.return_value = {"id": "test-vid"}
        mock_zai.videos.retrieve_videos_result.return_value = {
            "task_status": "SUCCESS",
            "video_result": [{"url": "http://fake.example.com/video.mp4"}],
        }
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.raise_for_status.side_effect = HTTPError("403 Forbidden")
        mock_get.return_value = mock_resp

        resp = client.post("/generate", json={"prompt": "test"})
        events = _parse_sse_events(resp.data)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "403" in error_events[0]["message"]


# --- chat-ui.md acceptance criteria (template verification) ---


def test_ui_has_send_button(client):
    """AC: 전송 버튼 존재"""
    resp = client.get("/")
    assert b"sendBtn" in resp.data


def test_ui_has_prompt_input(client):
    resp = client.get("/")
    assert b"promptInput" in resp.data


def test_ui_enter_key_sends(client):
    """AC: Enter 키로 전송"""
    resp = client.get("/")
    assert b"e.key === 'Enter'" in resp.data


def test_ui_shift_enter_newline(client):
    """AC: Shift+Enter는 줄바꿈"""
    resp = client.get("/")
    assert b"!e.shiftKey" in resp.data


def test_ui_input_disabled_during_generation(client):
    """AC: 생성 중 입력창 비활성화"""
    resp = client.get("/")
    assert b"setInputEnabled(false)" in resp.data
    assert b"setInputEnabled(true)" in resp.data


def test_ui_auto_scroll(client):
    """AC: 새 메시지 추가 시 자동 스크롤"""
    resp = client.get("/")
    assert b"scrollToBottom" in resp.data


def test_ui_empty_prompt_ignored(client):
    """AC: 빈 프롬프트 전송 불가"""
    resp = client.get("/")
    assert b"if (!prompt) return" in resp.data


def test_ui_download_link(client):
    """AC: 다운로드 링크"""
    resp = client.get("/")
    assert b"download=" in resp.data


def test_ui_video_player(client):
    """AC: 영상 플레이어에서 바로 재생 가능 (autoplay + muted for browser compat)"""
    resp = client.get("/")
    assert b"<video" in resp.data
    assert b"controls" in resp.data
    assert b"autoplay" in resp.data
    assert b"muted" in resp.data


def test_ui_progress_bar(client):
    """AC: 진행 바"""
    resp = client.get("/")
    assert b"progress-bar-fill" in resp.data


def test_ui_elapsed_text(client):
    """AC: 경과 시간 텍스트"""
    resp = client.get("/")
    html = resp.data.decode("utf-8")
    assert "초 경과" in html
