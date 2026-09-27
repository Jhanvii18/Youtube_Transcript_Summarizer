import streamlit as st
import time

from transcript_extractor import (
    get_video_metadata,
    get_transcript_with_timestamps,
)

from summarizer import (
    is_ollama_running,
    get_installed_models,
    generate_final_summary,
    generate_video_chapters,
    ask_video_question,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="YouTube Transcript Summarizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

html, body, [data-testid="stAppViewContainer"], .main {
    font-family: 'Outfit', sans-serif;
}

.header-title {
    background: linear-gradient(
        135deg,
        #6366f1 0%,
        #a855f7 50%,
        #ec4899 100%
    );

    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;

    font-weight: 800;
    font-size: 3rem;
    text-align: center;

    margin-bottom: .2rem;
    padding-top: 1rem;
}

.header-subtitle {
    color: #94a3b8;
    font-size: 1.15rem;
    text-align: center;
    margin-bottom: 2rem;
}

.video-card {
    background: rgba(255,255,255,.03);

    border: 1px solid rgba(255,255,255,.08);

    border-radius: 16px;

    padding: 1.5rem;

    margin-bottom: 2rem;

    display: flex;

    flex-wrap: wrap;

    gap: 1.5rem;

    align-items: center;
}

.video-thumb {
    border-radius: 10px;
    max-width: 240px;
}

.video-details {
    flex: 1;
    min-width: 280px;
}

.video-title {
    font-size: 1.4rem;
    font-weight: 700;
    margin-bottom: .5rem;
}

.video-channel {
    font-size: 1rem;
    color: #a855f7;
    font-weight: 600;
}

.video-meta-pills {
    display: flex;
    gap: .8rem;
    margin-top: .8rem;
    flex-wrap: wrap;
}

.video-pill {
    background: rgba(99,102,241,.15);

    color: #818cf8;

    border: 1px solid rgba(99,102,241,.3);

    padding: .3rem .8rem;

    border-radius: 20px;

    font-size: .85rem;
}

.status-badge-connected {
    background: rgba(34,197,94,.15);

    color: #4ade80;

    border: 1px solid rgba(34,197,94,.3);

    padding: .4rem 1rem;

    border-radius: 8px;

    font-weight: 600;

    text-align: center;

    margin-bottom: 1.5rem;
}

.status-badge-disconnected {
    background: rgba(239,68,68,.15);

    color: #f87171;

    border: 1px solid rgba(239,68,68,.3);

    padding: .4rem 1rem;

    border-radius: 8px;

    font-weight: 600;

    text-align: center;

    margin-bottom: 1.5rem;
}

.stat-box {
    background: rgba(255,255,255,.02);

    border: 1px solid rgba(255,255,255,.05);

    border-radius: 12px;

    padding: 1.2rem;

    text-align: center;
}

.stat-val {
    font-size: 1.8rem;

    font-weight: 800;

    color: #818cf8;
}

.stat-label {
    font-size: .85rem;

    color: #94a3b8;

    margin-top: .2rem;
}

.chapter-card {
    padding: .9rem 1rem;

    border: 1px solid rgba(255,255,255,.08);

    border-radius: 12px;

    margin-bottom: .7rem;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_duration(seconds):

    if not seconds:
        return "Unknown"

    seconds = int(seconds)

    hours, remainder = divmod(
        seconds,
        3600
    )

    minutes, seconds = divmod(
        remainder,
        60
    )

    if hours:

        return (
            f"{hours}h "
            f"{minutes}m "
            f"{seconds}s"
        )

    return (
        f"{minutes}m "
        f"{seconds}s"
    )


def format_timestamp(seconds):

    seconds = max(
        0,
        int(seconds)
    )

    hours, remainder = divmod(
        seconds,
        3600
    )

    minutes, seconds = divmod(
        remainder,
        60
    )

    if hours:

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def youtube_timestamp_url(
    video_id,
    seconds
):

    return (
        "https://www.youtube.com/watch?v="
        f"{video_id}"
        f"&t={int(seconds)}s"
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="header-title">'
    '⚡ YouTube Transcript Summarizer'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="header-subtitle">'
    'AI summaries, chapters, transcript search and video Q&A '
    '— powered locally by Ollama'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    "### ⚙️ Engine Settings"
)


ollama_host = st.sidebar.text_input(
    "Ollama Host URL",
    value="http://localhost:11434"
)


connected = is_ollama_running(
    ollama_host
)


if connected:

    st.sidebar.markdown(
        '<div class="status-badge-connected">'
        '● Ollama Connected'
        '</div>',
        unsafe_allow_html=True
    )

    models, model_err = (
        get_installed_models(
            ollama_host
        )
    )

    if model_err:

        st.sidebar.warning(
            f"Could not fetch model list: {model_err}"
        )

        models = []

else:

    st.sidebar.markdown(
        '<div class="status-badge-disconnected">'
        '● Ollama Offline'
        '</div>',
        unsafe_allow_html=True
    )

    st.sidebar.info(
        "Start Ollama locally, then refresh this page."
    )

    models = []


# ============================================================
# MODEL
# ============================================================

if models:

    preferred_order = [
        "qwen3:8b",
        "llama3.2:3b",
        "llama3.2:1b",
        "gemma2:2b",
        "llama3",
    ]

    default_idx = 0

    for preferred in preferred_order:

        for idx, model_name in enumerate(
            models
        ):

            if (
                preferred.lower()
                == model_name.lower()
            ):

                default_idx = idx

                break

        else:
            continue

        break


    selected_model = st.sidebar.selectbox(
        "🤖 Local LLM Model",
        options=models,
        index=default_idx
    )

else:

    selected_model = st.sidebar.text_input(
        "Local LLM Model",
        value="qwen3:8b"
    )


# ============================================================
# SUMMARY SETTINGS
# ============================================================

st.sidebar.markdown("---")


summary_mode = st.sidebar.selectbox(
    "📝 Summary Mode",

    [
        "Standard",
        "Student Notes",
        "Exam Revision",
        "Interview Preparation",
        "Action Plan",
    ]
)


detail_level = st.sidebar.select_slider(
    "Detail Level",

    options=[
        "Short",
        "Medium",
        "Long"
    ],

    value="Medium"
)


summary_language = st.sidebar.selectbox(
    "🌐 Summary Language",

    [
        "English",
        "Tamil",
        "Hindi",
        "Malayalam",
        "Telugu",
        "Kannada",
        "French",
        "Spanish",
        "German",
        "Japanese",
    ]
)


st.sidebar.markdown("---")


st.sidebar.caption(
    "🔒 Local & Private Mode — transcript "
    "and questions stay on your machine."
)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {

    "metadata": None,

    "transcript": None,

    "segments": [],

    "summary": None,

    "chapters": [],

    "stats": {},

    "qa_history": [],

}


for key, value in defaults.items():

    if key not in st.session_state:

        st.session_state[key] = value


# ============================================================
# YOUTUBE URL
# ============================================================

youtube_url = st.text_input(
    "🔗 Enter YouTube Video URL:",

    placeholder=(
        "https://www.youtube.com/watch?v=..."
    )
)


# ============================================================
# SUMMARIZE VIDEO
# ============================================================

if st.button(
    "⚡ Summarize Video"
):

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not youtube_url.strip():

        st.error(
            "Please enter a YouTube URL."
        )

        st.stop()


    if not connected:

        st.error(
            "Ollama is offline. "
            "Start Ollama and try again."
        )

        st.stop()


    # --------------------------------------------------------
    # RESET
    # --------------------------------------------------------

    st.session_state.metadata = None

    st.session_state.transcript = None

    st.session_state.segments = []

    st.session_state.summary = None

    st.session_state.chapters = []

    st.session_state.stats = {}

    st.session_state.qa_history = []


    start_time = time.time()


    # ========================================================
    # STAGE 1 — METADATA
    # ========================================================

    with st.status(
        "🚀 Processing video...",
        expanded=True
    ) as status:

        status.update(
            label="🔍 Getting video information...",
            state="running"
        )


        metadata, metadata_error = (
            get_video_metadata(
                youtube_url
            )
        )


        if metadata_error:

            status.update(
                label="❌ Metadata extraction failed",
                state="error"
            )

            st.error(
                metadata_error
            )

            st.stop()


        st.session_state.metadata = (
            metadata
        )


        # ====================================================
        # STAGE 2 — TRANSCRIPT
        # ====================================================

        status.update(
            label="📜 Getting transcript...",
            state="running"
        )


        extraction_start = time.time()


        (
            transcript,
            segments,
            transcript_error
        ) = get_transcript_with_timestamps(
            youtube_url
        )


        extraction_end = time.time()


        if transcript_error:

            status.update(
                label="❌ Transcript extraction failed",
                state="error"
            )

            st.error(
                transcript_error
            )

            st.stop()


        st.session_state.transcript = (
            transcript
        )

        st.session_state.segments = (
            segments
        )


        st.session_state.stats[
            "extract_time"
        ] = round(
            extraction_end
            - extraction_start,
            2
        )


        st.session_state.stats[
            "transcript_words"
        ] = len(
            transcript.split()
        )


        # ====================================================
        # STAGE 3 — FAST AI SUMMARY
        # ====================================================

        status.update(
            label="🧠 Generating summary with Ollama...",
            state="running"
        )


        summary_start = time.time()


        summary_box = st.empty()


        generator = generate_final_summary(

            transcript=transcript,

            model=selected_model,

            host=ollama_host,

            detail_level=detail_level,

            summary_mode=summary_mode,

            summary_language=summary_language
        )


        summary_text = ""


        for step in generator:

            if "error" in step:

                status.update(
                    label="❌ Summary generation failed",
                    state="error"
                )

                st.error(
                    step["error"]
                )

                st.stop()


            if "summary_so_far" in step:

                summary_text = (
                    step["summary_so_far"]
                )

                summary_box.markdown(
                    summary_text
                )


            elif "summary" in step:

                summary_text = (
                    step["summary"]
                )


            if "status" in step:

                status.update(
                    label=step["status"],
                    state="running"
                )


        summary_box.empty()


        if not summary_text:

            status.update(
                label="❌ No summary generated",
                state="error"
            )

            st.error(
                "Ollama did not return a summary."
            )

            st.stop()


        summary_end = time.time()


        st.session_state.summary = (
            summary_text
        )


        st.session_state.stats[
            "summarize_time"
        ] = round(
            summary_end
            - summary_start,
            2
        )


        st.session_state.stats[
            "summary_words"
        ] = len(
            summary_text.split()
        )


        # ====================================================
        # FINISHED
        # ====================================================

        st.session_state.stats[
            "total_time"
        ] = round(
            time.time()
            - start_time,
            2
        )


        status.update(
            label=(
                "✅ Summary completed! "
                "Chapters can be generated separately."
            ),
            state="complete"
        )


# ============================================================
# RESULTS
# ============================================================

if (
    st.session_state.summary
    and st.session_state.metadata
):

    meta = (
        st.session_state.metadata
    )

    video_id = meta[
        "video_id"
    ]


    # ========================================================
    # VIDEO CARD
    # ========================================================

    st.markdown(
        f"""<div class="video-card">
<img class="video-thumb"
src="{meta['thumbnail']}"
alt="Thumbnail">

<div class="video-details">

<div class="video-title">
{meta['title']}
</div>

<div class="video-channel">
👤 {meta['channel']}
</div>

<div class="video-meta-pills">

<div class="video-pill">
⏱️ Duration: {format_duration(meta['duration'])}
</div>

<div class="video-pill">
👁️ Views: {meta['view_count']:,}
</div>

<div class="video-pill">
📝 Mode: {summary_mode}
</div>

<div class="video-pill">
🌐 Language: {summary_language}
</div>

</div>

</div>
</div>""",
        unsafe_allow_html=True
    )


    # ========================================================
    # TABS
    # ========================================================

    (
        tab_summary,
        tab_chapters,
        tab_search,
        tab_qa,
        tab_transcript,
        tab_stats
    ) = st.tabs(
        [
            "📝 Summary",
            "🕐 Chapters",
            "🔍 Search",
            "💬 Ask Video",
            "📜 Transcript",
            "📊 Stats"
        ]
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    with tab_summary:

        st.markdown(
            st.session_state.summary
        )


        st.download_button(
            "💾 Download Summary (Markdown)",

            data=(
                st.session_state.summary
            ),

            file_name=(
                "Summary_"
                + meta["title"]
                .replace(" ", "_")[:40]
                + ".md"
            ),

            mime="text/markdown"
        )


    # ========================================================
    # CHAPTERS
    # ========================================================

    with tab_chapters:

        st.markdown(
            "### 🕐 AI Video Chapters"
        )


        st.info(
            "Chapters are generated on demand so "
            "they don't slow down your normal summary."
        )


        if st.button(
            "✨ Generate AI Chapters",
            key="generate_chapters"
        ):

            chapter_start = time.time()


            with st.spinner(
                "🧠 Ollama is generating chapters..."
            ):

                (
                    chapters,
                    chapter_error
                ) = generate_video_chapters(

                    segments=(
                        st.session_state.segments
                    ),

                    model=selected_model,

                    host=ollama_host,

                    max_chapters=12
                )


            chapter_end = time.time()


            if chapter_error:

                st.error(
                    chapter_error
                )

            else:

                st.session_state.chapters = (
                    chapters
                )

                st.session_state.stats[
                    "chapter_time"
                ] = round(
                    chapter_end
                    - chapter_start,
                    2
                )

                st.success(
                    f"Generated {len(chapters)} chapters!"
                )


        chapters = (
            st.session_state.chapters
        )


        if chapters:

            for chapter in chapters:

                timestamp = int(
                    chapter.get(
                        "start",
                        0
                    )
                )


                title = chapter.get(
                    "title",
                    "Untitled"
                )


                description = chapter.get(
                    "description",
                    ""
                )


                url = youtube_timestamp_url(
                    video_id,
                    timestamp
                )


                st.markdown(
                    f"""<div class="chapter-card">
<strong>
▶ {format_timestamp(timestamp)}
— {title}
</strong>
<br>
<span>{description}</span>
</div>""",
                    unsafe_allow_html=True
                )


                st.markdown(
                    f"[▶ Open at "
                    f"{format_timestamp(timestamp)}]"
                    f"({url})"
                )


        else:

            st.caption(
                "No chapters generated yet."
            )


    # ========================================================
    # SEARCH
    # ========================================================

    with tab_search:

        st.markdown(
            "### 🔍 Smart Transcript Search"
        )


        query = st.text_input(
            "Search transcript",

            placeholder=(
                "e.g. binary search, "
                "machine learning, formula..."
            ),

            key="transcript_search"
        )


        if query.strip():

            search_term = (
                query.strip().lower()
            )


            matches = [

                segment

                for segment
                in st.session_state.segments

                if search_term
                in segment["text"].lower()

            ]


            st.write(
                f"Found **{len(matches)} "
                "matching segment(s).**"
            )


            if matches:

                for index, segment in enumerate(
                    matches[:50],
                    start=1
                ):

                    start = int(
                        segment["start"]
                    )


                    timestamp_url = (
                        youtube_timestamp_url(
                            video_id,
                            start
                        )
                    )


                    st.markdown(
                        f"**{index}. "
                        f"[{format_timestamp(start)}]"
                        f"({timestamp_url})"
                        f"** — {segment['text']}"
                    )


            else:

                st.info(
                    "No matching transcript "
                    "segments found."
                )


    # ========================================================
    # ASK VIDEO
    # ========================================================

    with tab_qa:

        st.markdown(
            "### 💬 Ask Questions About This Video"
        )


        st.caption(
            "Ollama answers using the transcript."
        )


        question = st.text_input(
            "Your question",

            placeholder=(
                "What are the three main concepts "
                "explained in this video?"
            ),

            key="video_question"
        )


        if st.button(
            "🤖 Ask",
            key="ask_video"
        ):

            if not question.strip():

                st.warning(
                    "Please enter a question."
                )

            else:

                with st.spinner(
                    "🧠 Thinking..."
                ):

                    (
                        answer,
                        answer_error
                    ) = ask_video_question(

                        transcript=(
                            st.session_state.transcript
                        ),

                        question=question,

                        model=selected_model,

                        host=ollama_host
                    )


                if answer_error:

                    st.error(
                        answer_error
                    )

                else:

                    st.session_state.qa_history.append(
                        {
                            "question":
                                question,

                            "answer":
                                answer
                        }
                    )


        # ----------------------------------------------------
        # Q&A HISTORY
        # ----------------------------------------------------

        for item in reversed(
            st.session_state.qa_history
        ):

            st.markdown(
                f"**You:** "
                f"{item['question']}"
            )


            st.markdown(
                f"**🤖 Ollama:** "
                f"{item['answer']}"
            )


            st.markdown("---")


    # ========================================================
    # TRANSCRIPT
    # ========================================================

    with tab_transcript:

        st.markdown(
            "### 📜 Full Timestamped Transcript"
        )


        for segment in (
            st.session_state.segments
        ):

            start = int(
                segment["start"]
            )


            timestamp_url = (
                youtube_timestamp_url(
                    video_id,
                    start
                )
            )


            st.markdown(
                f"**[{format_timestamp(start)}]"
                f"({timestamp_url})**"
                f" — {segment['text']}"
            )


        st.download_button(
            "💾 Download Raw Transcript",

            data=(
                st.session_state.transcript
            ),

            file_name=(
                "Transcript_"
                + meta["title"]
                .replace(" ", "_")[:40]
                + ".txt"
            ),

            mime="text/plain"
        )


    # ========================================================
    # STATS
    # ========================================================

    with tab_stats:

        st.markdown(
            "### 📊 Performance & Diagnostics"
        )


        transcript_words = (
            st.session_state.stats.get(
                "transcript_words",
                0
            )
        )


        summary_words = (
            st.session_state.stats.get(
                "summary_words",
                0
            )
        )


        total_time = (
            st.session_state.stats.get(
                "total_time",
                0
            )
        )


        extract_time = (
            st.session_state.stats.get(
                "extract_time",
                0
            )
        )


        summarize_time = (
            st.session_state.stats.get(
                "summarize_time",
                0
            )
        )


        chapter_time = (
            st.session_state.stats.get(
                "chapter_time"
            )
        )


        reduction = round(
            (
                1
                - (
                    summary_words
                    / max(
                        transcript_words,
                        1
                    )
                )
            )
            * 100,
            1
        )


        c1, c2, c3, c4 = st.columns(4)


        with c1:

            st.markdown(
                f"""<div class="stat-box">

<div class="stat-val">
{transcript_words:,}
</div>

<div class="stat-label">
Transcript Words
</div>

</div>""",
                unsafe_allow_html=True
            )


        with c2:

            st.markdown(
                f"""<div class="stat-box">

<div class="stat-val">
{summary_words:,}
</div>

<div class="stat-label">
Summary Words
</div>

</div>""",
                unsafe_allow_html=True
            )


        with c3:

            st.markdown(
                f"""<div class="stat-box">

<div class="stat-val">
{reduction}%
</div>

<div class="stat-label">
Reading Time Saved
</div>

</div>""",
                unsafe_allow_html=True
            )


        with c4:

            st.markdown(
                f"""<div class="stat-box">

<div class="stat-val">
{total_time}s
</div>

<div class="stat-label">
Summary Processing Time
</div>

</div>""",
                unsafe_allow_html=True
            )


        st.write(
            f"- **Summary mode:** `{summary_mode}`"
        )


        st.write(
            f"- **Detail level:** `{detail_level}`"
        )


        st.write(
            f"- **Summary language:** `{summary_language}`"
        )


        st.write(
            f"- **Model:** `{selected_model}`"
        )


        st.write(
            f"- **Transcript extraction:** "
            f"`{extract_time}s`"
        )


        st.write(
            f"- **Summary generation:** "
            f"`{summarize_time}s`"
        )


        if chapter_time is not None:

            st.write(
                f"- **Chapter generation:** "
                f"`{chapter_time}s`"
            )

        else:

            st.write(
                "- **Chapter generation:** "
                "Not generated"
            )