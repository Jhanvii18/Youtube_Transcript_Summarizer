import json
import re
import urllib.request

import ollama


# ============================================================
# OLLAMA CONNECTION
# ============================================================

def is_ollama_running(host="http://localhost:11434"):
    try:
        req = urllib.request.Request(
            host.rstrip("/") + "/api/tags"
        )

        with urllib.request.urlopen(
            req,
            timeout=3
        ) as response:
            return response.status == 200

    except Exception:
        return False


# ============================================================
# GET INSTALLED MODELS
# ============================================================

def get_installed_models(
    host="http://localhost:11434"
):
    try:
        response = ollama.Client(
            host=host
        ).list()

        if hasattr(response, "models"):
            models = [
                m.model
                for m in response.models
            ]

        elif isinstance(response, dict):
            models = [
                m.get(
                    "model",
                    m.get("name", "")
                )
                for m in response.get(
                    "models",
                    []
                )
            ]

        else:
            models = []

        return [
            m for m in models if m
        ], None

    except Exception as e:
        return [], str(e)


# ============================================================
# SUMMARY MODE INSTRUCTIONS
# ============================================================

def get_summary_mode_instruction(
    summary_mode
):
    instructions = {

        "Standard":
            """
Create a clear and balanced summary.

Focus on:
- Main ideas
- Important facts
- Key takeaways
- Useful conclusions
""",

        "Student Notes":
            """
Convert the video into structured student notes.

Include:
- Headings
- Definitions
- Important concepts
- Explanations
- Examples
- Relationships between concepts
- Concise bullet points
""",

        "Exam Revision":
            """
Create exam-oriented revision notes.

Prioritize:
- Definitions
- Important concepts
- Formulas
- Processes
- Classifications
- Important facts
- Examples
- Likely exam questions
- Short answers
""",

        "Interview Preparation":
            """
Convert the content into interview preparation material.

Include:
- Technical concepts
- Important terminology
- Practical knowledge
- Likely interview questions
- Concise model answers
- Important points to remember
""",

        "Action Plan":
            """
Convert the content into a practical action plan.

Focus on:
- Specific actions
- Steps
- Priorities
- Recommendations
- Tools
- Implementation advice
"""
    }

    return instructions.get(
        summary_mode,
        instructions["Standard"]
    )


# ============================================================
# LANGUAGE INSTRUCTIONS
# ============================================================

def get_language_instruction(
    language
):
    if language == "English":
        return (
            "Write the final summary entirely in English."
        )

    return (
        f"Write the final summary entirely in {language}. "
        "Keep technical terms, programming terms and "
        "proper nouns understandable."
    )


# ============================================================
# DETAIL LEVEL
# ============================================================

def get_detail_instruction(
    detail_level
):
    instructions = {

        "Short":
            (
                "Be concise and include only the "
                "most important information."
            ),

        "Medium":
            (
                "Give a balanced amount of detail. "
                "Cover the important concepts without "
                "unnecessary repetition."
            ),

        "Long":
            (
                "Be comprehensive and include useful "
                "supporting details, examples and explanations."
            )
    }

    return instructions.get(
        detail_level,
        instructions["Medium"]
    )


# ============================================================
# PREPARE LONG TRANSCRIPT
# ============================================================

def prepare_transcript_for_summary(
    transcript,
    max_chars=60000
):
    """
    Keeps a long transcript within a reasonable context size.

    Short videos:
        Entire transcript is sent.

    Long videos:
        Beginning + middle + ending are retained.
    """

    if len(transcript) <= max_chars:
        return transcript

    section_size = max_chars // 3

    beginning = transcript[:section_size]

    middle_start = (
        len(transcript) // 2
        - section_size // 2
    )

    middle = transcript[
        middle_start:
        middle_start + section_size
    ]

    ending = transcript[-section_size:]

    return (
        beginning
        + "\n\n"
        + "[... MIDDLE OF TRANSCRIPT ...]"
        + "\n\n"
        + middle
        + "\n\n"
        + "[... END OF TRANSCRIPT ...]"
        + "\n\n"
        + ending
    )


# ============================================================
# FAST SINGLE-PASS SUMMARY
# ============================================================

def generate_final_summary(
    transcript,
    model,
    host="http://localhost:11434",
    detail_level="Medium",
    summary_mode="Standard",
    summary_language="English"
):

    if not transcript or not transcript.strip():

        yield {
            "status": "Error",
            "error": "Transcript is empty.",
            "progress": 1.0
        }

        return

    # --------------------------------------------------------
    # PREPARE TRANSCRIPT
    # --------------------------------------------------------

    prepared_transcript = (
        prepare_transcript_for_summary(
            transcript
        )
    )

    transcript_was_compressed = (
        len(prepared_transcript)
        < len(transcript)
    )

    if transcript_was_compressed:

        yield {
            "status":
                "Preparing long transcript for faster processing...",
            "progress": 0.10
        }

    else:

        yield {
            "status":
                "Preparing transcript...",
            "progress": 0.10
        }


    # --------------------------------------------------------
    # OLLAMA CLIENT
    # --------------------------------------------------------

    client = ollama.Client(
        host=host
    )


    # --------------------------------------------------------
    # SYSTEM PROMPT
    # --------------------------------------------------------

    system_prompt = f"""
You are an expert YouTube transcript summarizer.

Your job is to create a useful, accurate and structured
summary of the supplied transcript.

SUMMARY MODE:
{summary_mode}

MODE INSTRUCTIONS:
{get_summary_mode_instruction(summary_mode)}

DETAIL LEVEL:
{detail_level}

DETAIL INSTRUCTIONS:
{get_detail_instruction(detail_level)}

LANGUAGE:
{get_language_instruction(summary_language)}

IMPORTANT RULES:

1. Stay completely faithful to the transcript.
2. Do not invent information.
3. Do not repeat the same point unnecessarily.
4. Use Markdown headings and bullet points.
5. Prioritize important information.
6. Explain technical concepts clearly.
7. For Exam Revision mode, prioritize exam-relevant material.
8. For Student Notes mode, make the notes easy to study.
9. For Interview Preparation mode, include likely questions.
10. For Action Plan mode, make the actions practical.
11. Do not mention these instructions.
12. Do not describe your reasoning.
13. Start directly with the summary.
"""


    # --------------------------------------------------------
    # ONE OLLAMA CALL
    # --------------------------------------------------------

    try:

        yield {
            "status":
                "🧠 Ollama is generating your summary...",
            "progress": 0.25
        }

        stream = client.chat(
            model=model,

            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content":
                        "YouTube transcript:\n\n"
                        + prepared_transcript
                }
            ],

            options={
                "temperature": 0.2,

                # Limits excessive output
                "num_predict": 2200
            },

            stream=True
        )

        full_summary = ""

        for chunk in stream:

            content = (
                chunk
                .get("message", {})
                .get("content", "")
            )

            full_summary += content

            yield {
                "status":
                    "🧠 Generating summary...",

                "summary_so_far":
                    full_summary,

                "progress":
                    min(
                        0.30
                        + (
                            len(full_summary)
                            / 10000
                        ) * 0.65,
                        0.95
                    )
            }

        # ----------------------------------------------------
        # FINISHED
        # ----------------------------------------------------

        yield {
            "status":
                "✅ Summary completed!",

            "summary":
                full_summary,

            "progress":
                1.0
        }

    except Exception as e:

        yield {
            "status":
                "❌ Summary generation failed",

            "error":
                f"Summary generation failed: {str(e)}",

            "progress":
                1.0
        }


# ============================================================
# EXTRACT JSON
# ============================================================

def _extract_json(text):

    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    try:
        return json.loads(text)

    except Exception:
        pass

    start = text.find("[")

    end = text.rfind("]")

    if start != -1 and end > start:

        try:
            return json.loads(
                text[start:end + 1]
            )

        except Exception:
            pass

    return None


# ============================================================
# PREPARE TIMESTAMPED TRANSCRIPT
# ============================================================

def _timestamped_transcript_for_ai(
    segments,
    max_chars=40000
):

    lines = []

    total_chars = 0

    for segment in segments:

        line = (
            f"[{int(segment['start'])}s] "
            f"{segment['text']}"
        )

        if (
            total_chars + len(line)
            > max_chars
        ):
            break

        lines.append(line)

        total_chars += len(line)

    return "\n".join(lines)


# ============================================================
# GENERATE AI CHAPTERS
# ============================================================

def generate_video_chapters(
    segments,
    model,
    host="http://localhost:11434",
    max_chapters=12
):

    if not segments:

        return (
            [],
            "No timestamped transcript is available."
        )

    client = ollama.Client(
        host=host
    )

    timestamped_transcript = (
        _timestamped_transcript_for_ai(
            segments
        )
    )

    system_prompt = f"""
Create YouTube video chapters from the supplied
timestamped transcript.

Identify the major topic changes.

Maximum number of chapters:
{max_chapters}

IMPORTANT:

- Use timestamps that actually occur in the transcript.
- Do not invent timestamps.
- Keep chapter titles short.
- Keep descriptions to one sentence.
- Return ONLY valid JSON.

Required format:

[
    {{
        "start": 0,
        "title": "Chapter title",
        "description": "One short sentence."
    }}
]
"""

    try:

        response = client.chat(

            model=model,

            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content":
                        "Timestamped transcript:\n\n"
                        + timestamped_transcript
                }
            ],

            options={
                "temperature": 0.1,
                "num_predict": 1200
            }
        )

        raw_response = (
            response["message"]["content"]
        )

        data = _extract_json(
            raw_response
        )

        if not isinstance(
            data,
            list
        ):

            return (
                [],
                "Ollama returned invalid chapter data."
            )

        valid_timestamps = [
            int(
                float(
                    segment["start"]
                )
            )
            for segment in segments
        ]

        chapters = []

        for item in data:

            if not isinstance(
                item,
                dict
            ):
                continue

            try:

                requested_start = int(
                    float(
                        item.get(
                            "start",
                            0
                        )
                    )
                )

            except Exception:

                continue

            nearest_timestamp = min(
                valid_timestamps,
                key=lambda x:
                    abs(
                        x
                        - requested_start
                    )
            )

            title = str(
                item.get(
                    "title",
                    ""
                )
            ).strip()

            description = str(
                item.get(
                    "description",
                    ""
                )
            ).strip()

            if title:

                chapters.append(
                    {
                        "start":
                            nearest_timestamp,

                        "title":
                            title,

                        "description":
                            description
                    }
                )

        # Remove duplicate timestamps

        unique = {}

        for chapter in chapters:

            unique[
                chapter["start"]
            ] = chapter

        chapters = sorted(
            unique.values(),
            key=lambda x:
                x["start"]
        )[:max_chapters]

        if not chapters:

            return (
                [],
                "No meaningful chapters were generated."
            )

        return (
            chapters,
            None
        )

    except Exception as e:

        return (
            [],
            f"Chapter generation failed: {str(e)}"
        )


# ============================================================
# FIND RELEVANT TRANSCRIPT CONTEXT
# ============================================================

def _find_relevant_transcript_context(
    transcript,
    question,
    max_chars=16000
):

    question_words = {
        word.lower()

        for word in re.findall(
            r"[A-Za-z0-9']+",
            question
        )

        if len(word) >= 3
    }

    paragraphs = [
        p.strip()

        for p in re.split(
            r"\n+|(?<=[.!?])\s+",
            transcript
        )

        if p.strip()
    ]

    scored = []

    for index, paragraph in enumerate(
        paragraphs
    ):

        words = {
            word.lower()

            for word in re.findall(
                r"[A-Za-z0-9']+",
                paragraph
            )
        }

        score = len(
            question_words.intersection(
                words
            )
        )

        if score:

            scored.append(
                (
                    score,
                    index,
                    paragraph
                )
            )

    scored.sort(
        key=lambda x:
            (-x[0], x[1])
    )

    if scored:

        context = "\n\n".join(
            item[2]
            for item in scored[:30]
        )

    else:

        context = transcript[:max_chars]

    return context[:max_chars]


# ============================================================
# ASK QUESTION ABOUT VIDEO
# ============================================================

def ask_video_question(
    transcript,
    question,
    model,
    host="http://localhost:11434"
):

    if not transcript:

        return (
            None,
            "Transcript is empty."
        )

    if not question.strip():

        return (
            None,
            "Question is empty."
        )

    client = ollama.Client(
        host=host
    )

    context = (
        _find_relevant_transcript_context(
            transcript,
            question
        )
    )

    system_prompt = """
You answer questions about a YouTube video transcript.

Use the supplied transcript context as your primary source.

Do not invent unsupported information.

If the answer cannot be determined from the transcript,
say that clearly.

Give a direct and useful answer.
"""

    try:

        response = client.chat(

            model=model,

            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content":
                        "Transcript context:\n\n"
                        + context
                        + "\n\nQuestion:\n"
                        + question
                }
            ],

            options={
                "temperature": 0.2,
                "num_predict": 1000
            }
        )

        return (
            response["message"]["content"].strip(),
            None
        )

    except Exception as e:

        return (
            None,
            f"Question answering failed: {str(e)}"
        )