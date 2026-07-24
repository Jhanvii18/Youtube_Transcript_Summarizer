import ollama
import urllib.request
import json

def is_ollama_running(host='http://localhost:11434'):
    """
    Checks if the Ollama server is running and accessible at the host URL.
    """
    try:
        # Remove trailing slash if present
        url = host.rstrip('/') + '/api/tags'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status == 200
    except Exception:
        return False

def get_installed_models(host='http://localhost:11434'):
    """
    Retrieves a list of models currently installed in the local Ollama instance.
    """
    try:
        client = ollama.Client(host=host)
        response = client.list()
        # Handle different response formats dynamically (v0.6.0+ compatibility)
        if hasattr(response, 'models'):
            models = [m.model for m in response.models]
        elif isinstance(response, dict):
            models = [m.get('model', m.get('name', '')) for m in response.get('models', [])]
        elif hasattr(response, 'get'):
            models = [m.get('model', m.get('name', '')) for m in response.get('models', [])]
        else:
            models = []
            try:
                for m in response:
                    if hasattr(m, 'model'):
                        models.append(m.model)
                    elif hasattr(m, 'name'):
                        models.append(m.name)
            except Exception:
                pass
        return models, None
    except Exception as e:
        return [], str(e)

def chunk_text(text, max_words=2000, overlap=200):
    """
    Splits transcript text into overlapping chunks of words.
    Helps prevent context window overflow and local memory pressure.
    """
    words = text.split()
    if len(words) <= max_words:
        return [text]
    
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        if end == len(words):
            break
        # Advance by (max_words - overlap) to maintain overlap context
        start += (max_words - overlap)
    return chunks

def summarize_chunk(text, model, host='http://localhost:11434'):
    """
    Summarizes a single transcript chunk using Ollama.
    """
    client = ollama.Client(host=host)
    
    system_prompt = (
        "You are an expert content analyzer. Your task is to summarize the following segment of a YouTube video transcript. "
        "Extract key concepts, main ideas, and important facts. Keep your summary factual, concise, and structured. "
        "Do not include introductory or concluding conversational filler (like 'Here is a summary of...')."
    )
    
    user_prompt = f"Please summarize this part of the transcript:\n\n{text}"
    
    try:
        response = client.chat(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            options={
                'temperature': 0.3 # Low temperature for factual consistency
            }
        )
        return response['message']['content'], None
    except Exception as e:
        return None, str(e)

def generate_final_summary(transcript, model, host='http://localhost:11434', detail_level='Medium'):
    """
    Generates a structured final summary from a transcript.
    Uses single-pass summarization for short transcripts and a map-reduce chunking approach for long transcripts.
    """
    words = transcript.split()
    total_words = len(words)
    
    # Configure chunk size based on hardware limits and detail level
    max_words_per_chunk = 4000
    overlap = 100
    
    # For a short transcript (<= 1000 words), run a single direct pass
    if total_words <= 1000:
        yield {"status": "Processing single-pass summary...", "progress": 0.5}
        
        client = ollama.Client(host=host)
        system_prompt = (
            "You are an expert content analyzer. Analyze the YouTube video transcript and write a cohesive, premium-quality summary. "
            "Output MUST be formatted in Markdown as follows:\n\n"
            "### 📝 Executive Summary\n"
            "[A concise 2-3 sentence overview of the video's core message]\n\n"
            "### 🔑 Key Takeaways\n"
            "- [Key point 1]\n"
            "- [Key point 2]\n"
            "... (up to 10 points)\n\n"
            "### 🚀 Action Items & Next Steps\n"
            "- [Action item 1]\n"
            "- [Action item 2]\n"
            "...\n\n"
            "Keep the output professional, detailed, and directly useful. Do not mention meta-text like 'Based on the transcript provided' or conversational introductory sentences."
        )
        
        user_prompt = f"Here is the transcript of the video:\n\n{transcript}"
        
        try:
            response_stream = client.chat(
                model=model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                options={'temperature': 0.3},
                stream=True
            )
            full_response = ""
            for chunk in response_stream:
                content = chunk.get('message', {}).get('content', '')
                full_response += content
                yield {
                    "status": "Generating summary...",
                    "summary_so_far": full_response,
                    "progress": 0.5 + (0.4 * min(len(full_response) / 2000, 1.0))
                }
            yield {"status": "Done!", "summary": full_response, "progress": 1.0}
        except Exception as e:
            yield {"status": "Error", "error": f"Failed to generate summary: {str(e)}", "progress": 1.0}
        return

    # For a long transcript, run a map-reduce chunked summarization
    chunks = chunk_text(transcript, max_words=max_words_per_chunk, overlap=overlap)
    num_chunks = len(chunks)
    
    yield {"status": f"Transcript split into {num_chunks} chunks. Summarizing chunks...", "progress": 0.1}
    
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        yield {"status": f"Summarizing segment {i+1} of {num_chunks}...", "progress": 0.1 + (i / num_chunks) * 0.7}
        summary, err = summarize_chunk(chunk, model, host)
        if err:
            yield {"status": "Error", "error": f"Failed on segment {i+1}: {err}", "progress": 1.0}
            return
        chunk_summaries.append(summary)
        
    yield {"status": "Synthesizing final structured summary...", "progress": 0.85}
    
    combined_summaries = "\n\n--- NEXT SEGMENT SUMMARY ---\n\n".join(chunk_summaries)
    
    client = ollama.Client(host=host)
    system_prompt = (
        "You are an expert summarizer. Synthesize the section summaries of a YouTube video into a single, cohesive, premium-quality final summary. "
        "Output MUST be formatted in Markdown as follows:\n\n"
        "### 📝 Executive Summary\n"
        "[A concise 2-3 sentence overview of the video's core message synthesis]\n\n"
        "### 🔑 Key Takeaways\n"
        "- [Key point 1]\n"
        "- [Key point 2]\n"
        "... (up to 10 points)\n\n"
        "### 🚀 Action Items & Next Steps\n"
        "- [Action item 1]\n"
        "- [Action item 2]\n"
        "...\n\n"
        "Ensure all details are factual and capture the core concepts of the video. Do not add chatty intros."
    )
    
    user_prompt = f"Here are the section summaries of the video:\n\n{combined_summaries}"
    
    try:
        response_stream = client.chat(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            options={'temperature': 0.3},
            stream=True
        )
        full_response = ""
        for chunk in response_stream:
            content = chunk.get('message', {}).get('content', '')
            full_response += content
            yield {
                "status": "Synthesizing final summary...",
                "summary_so_far": full_response,
                "progress": 0.85 + (0.14 * min(len(full_response) / 2000, 1.0))
            }
        yield {"status": "Done!", "summary": full_response, "progress": 1.0}
    except Exception as e:
        yield {"status": "Error", "error": f"Failed to generate final synthesis: {str(e)}", "progress": 1.0}
