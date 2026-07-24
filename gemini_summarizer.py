from google import genai
from google.genai import types

GEMINI_MODELS = [
    "gemini-3.1-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
]


def get_available_gemini_models(api_key: str) -> tuple[list, object]:
    """
    Dynamically fetches all text-generation capable Gemini models available
    on the given API key. Returns (model_list, error_or_None).
    """
    try:
        client = genai.Client(api_key=api_key)
        all_models = list(client.models.list())
        # Filter to models that support generateContent and are Gemini models
        chat_models = [
            m.name.replace("models/", "")
            for m in all_models
            if m.name and "gemini" in m.name.lower()
            and hasattr(m, 'supported_actions')
            and any("generateContent" in str(a) for a in (m.supported_actions or []))
        ]
        # Fallback: if filtering returns nothing, grab any gemini model
        if not chat_models:
            chat_models = [
                m.name.replace("models/", "")
                for m in all_models
                if m.name and "gemini" in m.name.lower()
            ]
        # Sort: flash models first (faster), pro models last
        chat_models.sort(key=lambda x: ("pro" in x, x))
        return chat_models if chat_models else GEMINI_MODELS, None
    except Exception as e:
        return GEMINI_MODELS, str(e)


def validate_gemini_api_key(api_key: str) -> tuple[bool, object]:
    """
    Validates the Gemini API key by attempting a lightweight models list call.
    Returns (True, None) on success, (False, error_message) on failure.
    """
    try:
        client = genai.Client(api_key=api_key)
        models = list(client.models.list())
        if models:
            return True, None
        return False, "No models returned. Check your API key."
    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "invalid" in err.lower() or "401" in err:
            return False, "Invalid API key. Please check your Gemini API key."
        return False, f"Connection error: {err}"


def generate_final_summary_gemini(transcript: str, api_key: str, model_name: str = "gemini-2.5-flash", detail_level: str = "Medium"):
    """
    Generates a structured final summary using the Gemini API (google.genai SDK).
    Uses a single-pass approach — Gemini handles very long contexts natively.
    Yields progress dicts in the same format as the Ollama summarizer.
    """
    # Detail level -> instruction mapping
    detail_instructions = {
        "Short":  "Keep the summary brief and concise. Max 5 key takeaways, 2-sentence executive summary.",
        "Medium": "Provide a balanced summary with up to 8 key takeaways.",
        "Long":   "Provide a comprehensive, detailed summary with up to 12 key takeaways and thorough action items.",
    }
    detail_instruction = detail_instructions.get(detail_level, detail_instructions["Medium"])

    system_prompt = (
        f"You are an expert content analyzer. Analyze this YouTube video transcript and write a cohesive, premium-quality summary.\n"
        f"{detail_instruction}\n\n"
        "Output MUST be formatted in Markdown exactly as follows:\n\n"
        "### 📝 Executive Summary\n"
        "[A concise 2-3 sentence overview of the video's core message]\n\n"
        "### 🔑 Key Takeaways\n"
        "- [Key point 1]\n"
        "- [Key point 2]\n"
        "...\n\n"
        "### 🚀 Action Items & Next Steps\n"
        "- [Action item 1]\n"
        "- [Action item 2]\n"
        "...\n\n"
        "Keep the output professional, detailed, and directly useful. "
        "Do not add conversational intros like 'Based on the transcript provided' or 'Here is a summary'."
    )

    full_prompt = f"{system_prompt}\n\nHere is the transcript of the video:\n\n{transcript}"

    yield {"status": "Connecting to Gemini API...", "progress": 0.1}

    try:
        client = genai.Client(api_key=api_key)

        yield {"status": f"Generating summary with {model_name}...", "progress": 0.2}

        # Use streaming for live output
        full_response = ""
        stream = client.models.generate_content_stream(
            model=model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                system_instruction=system_prompt,
            ),
        )
        for chunk in stream:
            if chunk.text:
                full_response += chunk.text
                progress = min(0.2 + (0.75 * min(len(full_response) / 2000, 1.0)), 0.95)
            yield {
                "status": f"Generating summary with {model_name}...",
                    "summary_so_far": full_response,
                "progress": progress,
            }

        yield {"status": "Done!", "summary": full_response, "progress": 1.0}

    except Exception as e:
        err = str(e)
        if "quota" in err.lower() or "429" in err:
            yield {"status": "Error", "error": "Gemini API quota exceeded. Try again later or switch to a different model.", "progress": 1.0}
        elif "api_key" in err.lower() or "API_KEY" in err or "401" in err:
            yield {"status": "Error", "error": "Invalid Gemini API key. Please re-enter your key in the sidebar.", "progress": 1.0}
        else:
            yield {"status": "Error", "error": f"Gemini API error: {err}", "progress": 1.0}
