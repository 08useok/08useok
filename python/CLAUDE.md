# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Scripts for generating videos via the ZAI API (CogVideoX-3 model). Videos are saved to `videos/`.

## Running Scripts

```bash
python cogvideox_text.py        # text-to-video (prompt.txt → video)
python cogvideox_image.py       # single image + prompt → video
python cogvideox_image_two.py   # first & last frame images + prompt → video
```

## Architecture

All three scripts share the same pattern:
1. Read prompt from `prompt.txt`
2. Submit generation request to `client.videos.generations()`
3. Poll `client.videos.retrieve_videos_result(id=video_id)` every second until `task_status == "SUCCESS"`
4. Download the resulting video to `videos/`

`_get_attr_or_key(obj, key)` is a helper used in all scripts to handle both dict and object-style API responses.

## Key Details

- **Model**: `cogvideox-3` via `ZaiClient` (`zai` package)
- **Prompt**: Edit `prompt.txt` to change what video is generated
- **Output**: `videos/` directory (auto-created); filename derived from `ufileattname` query param or URL path
- **API key**: Hardcoded in each script — move to an env var if sharing code
- **`cogvideox_image_two.py`**: Takes two image URLs (`first_image_frame`, `last_image_frame`) to control start/end frames
