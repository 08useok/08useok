import warnings
warnings.filterwarnings("ignore")

import json
import os
import time

import requests
from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from zai import ZaiClient

app = Flask(__name__)

client = ZaiClient(api_key="e39e9d8edc8948f98925ed38e95d7552.VOkcfLaUaX4MokJC")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")
os.makedirs(VIDEOS_DIR, exist_ok=True)


def _get_attr_or_key(obj, key):
    """Handle both dict and object-style API responses."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "잘못된 요청 형식입니다."}), 400
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "프롬프트를 입력해주세요."}), 400

    def stream():
        try:
            response = client.videos.generations(
                model="cogvideox-3",
                prompt=prompt,
                quality="quality",
                with_audio=False,
                size="1920x1080",
                fps=60,
            )

            video_id = _get_attr_or_key(response, "id")
            if not video_id:
                request_id = _get_attr_or_key(response, "request_id")
                if request_id:
                    video_id = request_id
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': '비디오 ID를 가져올 수 없습니다.'})}\n\n"
                    return

            start_time = time.time()

            MAX_POLL_SECONDS = 600  # 10-minute safety limit

            while True:
                result = client.videos.retrieve_videos_result(id=video_id)
                elapsed = int(time.time() - start_time) + 1
                status = _get_attr_or_key(result, "task_status")
                percent = min(elapsed / 240 * 100, 95)

                if elapsed > MAX_POLL_SECONDS:
                    yield f"data: {json.dumps({'type': 'error', 'message': '생성 시간이 초과되었습니다 (10분).'})}\n\n"
                    return

                if status == "SUCCESS":
                    yield f"data: {json.dumps({'type': 'progress', 'elapsed': elapsed, 'percent': 100})}\n\n"

                    video_results = _get_attr_or_key(result, "video_result")
                    if not video_results:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'video_result가 없습니다.'})}\n\n"
                        return

                    first = video_results[0]
                    url = _get_attr_or_key(first, "url")
                    if not url:
                        yield f"data: {json.dumps({'type': 'error', 'message': '동영상 URL을 찾을 수 없습니다.'})}\n\n"
                        return

                    existing = [f for f in os.listdir(VIDEOS_DIR) if f.endswith("_video.mp4")]
                    filename = f"{len(existing) + 1}_video.mp4"
                    out_path = os.path.join(VIDEOS_DIR, filename)

                    with requests.get(url, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(out_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)

                    yield f"data: {json.dumps({'type': 'done', 'filename': filename})}\n\n"
                    return

                elif status == "FAIL":
                    yield f"data: {json.dumps({'type': 'error', 'message': '영상 생성에 실패했습니다.'})}\n\n"
                    return

                else:
                    yield f"data: {json.dumps({'type': 'progress', 'elapsed': elapsed, 'percent': round(percent)})}\n\n"

                time.sleep(1)

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/videos/<filename>")
def serve_video(filename):
    return send_from_directory(VIDEOS_DIR, filename, conditional=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
