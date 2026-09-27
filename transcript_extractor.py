import glob
import json
import os
import re
import tempfile

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi


# ============================================================
# EXTRACT YOUTUBE VIDEO ID
# ============================================================

def extract_video_id(url):

    pattern = (
        r"(?:https?://)?(?:www\.)?"
        r"(?:youtube\.com/"
        r"(?:[^/\n\s]+/\S+/|"
        r"(?:v|e(?:mbed)?)\/|"
        r"\S*?[?&]v=)"
        r"([a-zA-Z0-9_-]{11})"
        r"|youtu\.be/"
        r"([a-zA-Z0-9_-]{11}))"
    )

    match = re.search(
        pattern,
        url,
    )

    if not match:
        return None

    return (
        match.group(1)
        or match.group(2)
    )


# ============================================================
# VIDEO METADATA
# ============================================================

def get_video_metadata(url):

    video_id = extract_video_id(url)

    try:

        with yt_dlp.YoutubeDL(
            {
                "skip_download": True,
                "quiet": True,
                "no_warnings": True,
            }
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False,
            )

        return {
            "video_id": video_id,
            "title": info.get(
                "title",
                "Unknown Title",
            ),
            "channel": info.get(
                "uploader",
                "Unknown Channel",
            ),
            "thumbnail": info.get(
                "thumbnail",
                "",
            ),
            "duration": info.get(
                "duration",
                0,
            ) or 0,
            "view_count": info.get(
                "view_count",
                0,
            ) or 0,
        }, None

    except Exception as e:

        return (
            None,
            f"Failed to retrieve metadata: {str(e)}",
        )


# ============================================================
# CLEAN TEXT
# ============================================================

def _clean_text(text):

    text = re.sub(
        r"<[^>]+>",
        "",
        text or "",
    )

    text = text.replace(
        "&nbsp;",
        " ",
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================
# REMOVE DUPLICATE SEGMENTS
# ============================================================

def _deduplicate_segments(segments):

    cleaned = []
    previous = None

    for seg in sorted(
        segments,
        key=lambda x: float(
            x.get("start", 0)
        ),
    ):

        text = _clean_text(
            seg.get(
                "text",
                "",
            )
        )

        if not text:
            continue

        if text == previous and cleaned:
            continue

        cleaned.append(
            {
                "text": text,
                "start": float(
                    seg.get(
                        "start",
                        0,
                    )
                ),
                "duration": float(
                    seg.get(
                        "duration",
                        0,
                    )
                ),
            }
        )

        previous = text

    return cleaned


# ============================================================
# YOUTUBE TRANSCRIPT API
# ============================================================

def _fetch_api_segments(video_id):

    api = YouTubeTranscriptApi()

    transcript_list = api.list(
        video_id
    )

    transcript = None

    # Prefer English
    try:

        transcript = transcript_list.find_transcript(
            ["en"]
        )

    except Exception:

        # Try Hindi / Urdu
        try:

            transcript = transcript_list.find_transcript(
                ["hi", "ur"]
            )

        except Exception:

            available = list(
                transcript_list
            )

            if not available:
                return (
                    None,
                    "No transcripts available for this video.",
                )

            transcript = available[0]

    fetched = transcript.fetch()

    segments = []

    for item in fetched:

        if hasattr(item, "text"):

            text = item.text
            start = item.start
            duration = item.duration

        elif isinstance(item, dict):

            text = item.get(
                "text",
                "",
            )

            start = item.get(
                "start",
                0,
            )

            duration = item.get(
                "duration",
                0,
            )

        else:
            continue

        segments.append(
            {
                "text": text,
                "start": float(start),
                "duration": float(duration),
            }
        )

    segments = _deduplicate_segments(
        segments
    )

    if segments:

        return segments, None

    return (
        None,
        "Transcript was found, but it contained no readable text.",
    )


# ============================================================
# PARSE JSON3 SUBTITLES
# ============================================================

def _parse_json3(content):

    data = json.loads(
        content
    )

    segments = []

    for event in data.get(
        "events",
        [],
    ):

        start_ms = event.get(
            "tStartMs",
            0,
        )

        duration_ms = event.get(
            "dDurationMs",
            0,
        )

        text = _clean_text(
            "".join(
                seg.get(
                    "utf8",
                    "",
                )
                for seg in event.get(
                    "segs",
                    [],
                )
            )
        )

        if text:

            segments.append(
                {
                    "text": text,
                    "start": (
                        float(start_ms)
                        / 1000
                    ),
                    "duration": (
                        float(duration_ms)
                        / 1000
                    ),
                }
            )

    return _deduplicate_segments(
        segments
    )


# ============================================================
# PARSE WEBVTT
# ============================================================

def _parse_vtt(content):

    lines = content.splitlines()

    segments = []
    i = 0

    def parse_time(value):

        parts = (
            value
            .replace(",", ".")
            .split(":")
        )

        if len(parts) == 3:

            return (
                int(parts[0]) * 3600
                + int(parts[1]) * 60
                + float(parts[2])
            )

        return (
            int(parts[0]) * 60
            + float(parts[1])
        )

    while i < len(lines):

        line = lines[i].strip()

        if "-->" not in line:

            i += 1
            continue

        times = line.split(
            "-->"
        )

        try:

            start = parse_time(
                times[0]
                .strip()
                .split(" ")[0]
            )

            end = parse_time(
                times[1]
                .strip()
                .split(" ")[0]
            )

        except Exception:

            i += 1
            continue

        i += 1

        text_lines = []

        while (
            i < len(lines)
            and lines[i].strip()
        ):

            text_lines.append(
                lines[i].strip()
            )

            i += 1

        text = _clean_text(
            " ".join(text_lines)
        )

        if text:

            segments.append(
                {
                    "text": text,
                    "start": start,
                    "duration": max(
                        0,
                        end - start,
                    ),
                }
            )

        i += 1

    return _deduplicate_segments(
        segments
    )


# ============================================================
# BASIC SUBTITLE PARSER
# ============================================================

def _parse_basic_subtitles(content):

    text = _clean_text(
        " ".join(
            line.strip()
            for line in content.splitlines()
            if (
                line.strip()
                and not line.strip().isdigit()
                and "-->" not in line
            )
        )
    )

    if text:

        return [
            {
                "text": text,
                "start": 0.0,
                "duration": 0.0,
            }
        ]

    return []


# ============================================================
# YT-DLP FALLBACK
# ============================================================

def _fetch_yt_dlp_segments(url):

    with tempfile.TemporaryDirectory() as temp_dir:

        outtmpl = os.path.join(
            temp_dir,
            "subs",
        )

        opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
        }

        try:

            with yt_dlp.YoutubeDL(
                opts
            ) as ydl:

                ydl.download([url])

            files = glob.glob(
                os.path.join(
                    temp_dir,
                    "subs.en.*",
                )
            )

            if not files:

                return (
                    None,
                    "No English subtitles or automatic captions found.",
                )

            files.sort(
                key=lambda p:
                    0 if p.endswith(".json3")
                    else 1
            )

            path = files[0]

            with open(
                path,
                "r",
                encoding="utf-8",
            ) as f:

                content = f.read()

            if path.endswith(".json3"):

                segments = _parse_json3(
                    content
                )

            elif path.endswith(".vtt"):

                segments = _parse_vtt(
                    content
                )

            else:

                segments = _parse_basic_subtitles(
                    content
                )

            if segments:

                return segments, None

            return (
                None,
                "Subtitle file was found, but no readable captions were parsed.",
            )

        except Exception as e:

            return (
                None,
                f"yt-dlp subtitle download failed: {str(e)}",
            )


# ============================================================
# MAIN TRANSCRIPT FUNCTION
# ============================================================

def get_transcript_with_timestamps(url):

    video_id = extract_video_id(
        url
    )

    if not video_id:

        return (
            None,
            [],
            "Invalid YouTube URL format.",
        )

    try:

        segments, err = _fetch_api_segments(
            video_id
        )

    except Exception as e:

        segments = None
        err = str(e)

    if segments:

        transcript = " ".join(
            seg["text"]
            for seg in segments
        )

        return (
            transcript,
            segments,
            None,
        )

    print(
        "youtube-transcript-api failed "
        f"({err}). Retrying with yt-dlp fallback..."
    )

    segments, fallback_err = (
        _fetch_yt_dlp_segments(
            url
        )
    )

    if segments:

        transcript = " ".join(
            seg["text"]
            for seg in segments
        )

        return (
            transcript,
            segments,
            None,
        )

    return (
        None,
        [],
        "Transcript extraction failed. "
        f"API error: {err}. "
        f"Fallback error: {fallback_err}",
    )


# ============================================================
# BACKWARD-COMPATIBLE FUNCTION
# ============================================================

def get_transcript(url):

    transcript, _, err = (
        get_transcript_with_timestamps(
            url
        )
    )

    return transcript, err