import re
import json
import urllib.request
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

def extract_video_id(url):
    """
    Extracts the 11-character YouTube video ID from a URL.
    """
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_video_metadata(url):
    """
    Fetches video metadata (title, channel, thumbnail, duration) using yt-dlp.
    """
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            metadata = {
                'title': info.get('title', 'Unknown Title'),
                'channel': info.get('uploader', 'Unknown Channel'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0), # in seconds
                'view_count': info.get('view_count', 0),
            }
            return metadata, None
    except Exception as e:
        return None, f"Failed to retrieve metadata: {str(e)}"

def get_transcript_via_api(video_id):
    """
    Attempts to fetch transcript using the youtube-transcript-api.
    Prefers English, falls back to Hindi/Urdu, and finally falls back to any available language.
    """
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        # 1. Try finding manually created or generated English transcript
        try:
            transcript = transcript_list.find_transcript(['en'])
        except Exception:
            try:
                # 2. Try Hindi or Urdu (very common fallback languages)
                transcript = transcript_list.find_transcript(['hi', 'ur'])
            except Exception:
                # 3. Get the first available transcript in the list
                transcripts_available = list(transcript_list)
                if transcripts_available:
                    transcript = transcripts_available[0]
                else:
                    return None, "No transcripts available for this video."
            
        data = transcript.fetch()
        text = " ".join([item.text for item in data])
        cleaned_text = re.sub(r'\s+', ' ', text).strip()
        return cleaned_text, None
    except Exception as e:
        return None, str(e)

def get_transcript_via_yt_dlp(url):
    """
    Fallback method using yt-dlp to download subtitle/captions directly using
    yt-dlp's internal downloading engine, avoiding HTTP 429 rate limit blocks.
    """
    import tempfile
    import os
    import glob
    
    # Create a temporary directory to save the downloaded subtitles
    with tempfile.TemporaryDirectory() as temp_dir:
        # Define output template for the subtitle file
        outtmpl = os.path.join(temp_dir, 'subs')
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            # Check for downloaded files starting with 'subs.en.'
            # yt-dlp saves them as 'subs.en.vtt', 'subs.en.json3', or 'subs.en.srv3'
            sub_files = glob.glob(os.path.join(temp_dir, 'subs.en.*'))
            if not sub_files:
                return None, "No English subtitles or automatic captions downloaded by yt-dlp."
                
            sub_file_path = sub_files[0]
            with open(sub_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse according to format
            if sub_file_path.endswith('.json3'):
                data = json.loads(content)
                text_parts = []
                for event in data.get('events', []):
                    if 'segs' in event:
                        for seg in event['segs']:
                            utf8_text = seg.get('utf8', '').strip()
                            if utf8_text and not utf8_text.startswith('\n'):
                                text_parts.append(utf8_text)
                cleaned_text = re.sub(r'\s+', ' ', " ".join(text_parts)).strip()
                return cleaned_text, None
                
            elif sub_file_path.endswith('.vtt'):
                lines = content.split('\n')
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if (not line or 
                        line.startswith('WEBVTT') or 
                        line.startswith('Kind:') or 
                        line.startswith('Language:') or 
                        line.startswith('Style:') or
                        '-->' in line or 
                        line.isdigit()):
                        continue
                    line_clean = re.sub(r'<[^>]+>', '', line)
                    if line_clean:
                        cleaned_lines.append(line_clean)
                
                # De-duplicate lines (VTT often repeats lines)
                unique_lines = []
                for cl in cleaned_lines:
                    if not unique_lines or unique_lines[-1] != cl:
                        unique_lines.append(cl)
                return " ".join(unique_lines), None
                
            else:
                # Basic parsing for SRT / other formats
                lines = content.split('\n')
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if not line or line.isdigit() or '-->' in line:
                        continue
                    cleaned_lines.append(line)
                return " ".join(cleaned_lines), None
                
        except Exception as e:
            return None, f"yt-dlp subtitle download failed: {str(e)}"

def get_transcript(url):
    """
    Main entry point for extracting the transcript.
    Attempts youtube-transcript-api first, then falls back to yt-dlp.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None, "Invalid YouTube URL format."
    
    # Try youtube-transcript-api (fastest & cleanest)
    transcript, err = get_transcript_via_api(video_id)
    if transcript:
        return transcript, None
    
    # Try yt-dlp (reliable fallback)
    print(f"youtube-transcript-api failed ({err}). Retrying with yt-dlp fallback...")
    return get_transcript_via_yt_dlp(url)

if __name__ == "__main__":
    # Quick CLI test
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Never Gonna Give You Up
    print("Testing extractor.py with URL:", test_url)
    meta, err = get_video_metadata(test_url)
    if err:
        print("Metadata error:", err)
    else:
        print("Metadata title:", meta['title'])
        print("Metadata channel:", meta['channel'])
        
    transcript, err = get_transcript(test_url)
    if err:
        print("Transcript error:", err)
    else:
        print("Transcript preview (first 200 chars):", transcript[:200])
