import warnings
warnings.filterwarnings("ignore")

from zai import ZaiClient
import time
import os
import requests

client = ZaiClient(api_key="e39e9d8edc8948f98925ed38e95d7552.VOkcfLaUaX4MokJC")
base_dir = os.path.dirname(os.path.abspath(__file__))
prompt_path = os.path.join(base_dir, "prompt.txt")

try:
    with open(prompt_path, "r", encoding="utf-8") as f:
        v_prompt = f.read()
except Exception as e:
    print(f"prompt.txt 로드 실패: {e}")
    v_prompt = ""

def _get_attr_or_key(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)

image_url = "https://img.iplaysoft.com/wp-content/uploads/2019/free-images/free_stock_photo.jpg"

response = client.videos.generations(
    model="cogvideox-3",
    image_url=image_url,
    prompt=v_prompt,
    quality="quality",
    with_audio=True,
    size="1920x1080",
    fps=30,
)

print("비디오 생성 시작...")
print("************************")
print(v_prompt)
print("************************")

video_id = _get_attr_or_key(response, "id")
if not video_id:
    request_id = _get_attr_or_key(response, "request_id")
    if request_id:
        video_id = request_id
    else:
        raise RuntimeError(f"비디오 ID를 가져올 수 없습니다: {response}")

print(f"비디오 ID: {video_id}")
print("비디오 생성이 완료될 때까지 기다려주세요...")

start_time = time.time()
videos_dir = os.path.join(base_dir, "videos")
os.makedirs(videos_dir, exist_ok=True)

try:
    while True:
        result = client.videos.retrieve_videos_result(id=video_id)
        elapsed = int(time.time() - start_time) + 1
        status = _get_attr_or_key(result, "task_status")
        print(f"{elapsed}초 - {video_id} : 동영상을 생성 중입니다... {status}")

        if status == "SUCCESS":
            print("작업 완료")
            time.sleep(5)
            video_results = _get_attr_or_key(result, "video_result")
            if not video_results:
                print("video_result가 없습니다.")
                break

            first = video_results[0]
            url = _get_attr_or_key(first, "url")
            if not url:
                print("동영상 URL을 찾을 수 없습니다.")
                break

            existing = [f for f in os.listdir(videos_dir) if f.endswith("_video.mp4")]
            filename = f"{len(existing) + 1}_video.mp4"
            out_path = os.path.join(videos_dir, filename)

            print(f"다운로드 시작: {url} -> {out_path}")
            try:
                with requests.get(url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                print(f"다운로드 완료: {out_path}")
            except Exception as e:
                print(f"다운로드 실패: {e}")
            break

        time.sleep(1)

except KeyboardInterrupt:
    print("루프 중지")
