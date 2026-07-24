import streamlit as st
import time
import os
from transcript_extractor import get_video_metadata, get_transcript
from summarizer import is_ollama_running, get_installed_models, generate_final_summary
from gemini_summarizer import generate_final_summary_gemini, validate_gemini_api_key, get_available_gemini_models, GEMINI_MODELS

# Set page configurations
st.set_page_config(
    page_title="YouTube Transcript Summarizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium CSS styling (Dark theme optimized with glassmorphic cards and gradients)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

/* Typography & General */
html, body, [data-testid="stAppViewContainer"], .main {
    font-family: 'Outfit', sans-serif;
}

/* Gradient Header Title */
.header-title {
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    font-size: 3rem;
    text-align: center;
    margin-bottom: 0.2rem;
    padding-top: 1rem;
}

.header-subtitle {
    color: #94a3b8;
    font-size: 1.15rem;
    text-align: center;
    margin-bottom: 2rem;
    font-weight: 400;
}

/* Video Info Card */
.video-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 2rem;
    backdrop-filter: blur(8px);
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
    align-items: center;
}

.video-thumb {
    border-radius: 10px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
    max-width: 240px;
    height: auto;
}

.video-details {
    flex: 1;
    min-width: 280px;
}

.video-title {
    font-size: 1.4rem;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 0.5rem;
    line-height: 1.3;
}

.video-channel {
    font-size: 1rem;
    color: #a855f7;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.video-meta-pills {
    display: flex;
    gap: 0.8rem;
    margin-top: 0.8rem;
    flex-wrap: wrap;
}

.video-pill {
    background: rgba(99, 102, 241, 0.15);
    color: #818cf8;
    border: 1px solid rgba(99, 102, 241, 0.3);
    padding: 0.3rem 0.8rem;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 500;
}

/* Sidebar Connected Status Badge */
.status-badge-connected {
    background: rgba(34, 197, 94, 0.15);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.3);
    padding: 0.4rem 1rem;
    border-radius: 8px;
    font-weight: 600;
    text-align: center;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

.status-badge-disconnected {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
    padding: 0.4rem 1rem;
    border-radius: 8px;
    font-weight: 600;
    text-align: center;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

/* Stats Styling */
.stat-box {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
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
    font-size: 0.85rem;
    color: #94a3b8;
    margin-top: 0.2rem;
}
</style>
""", unsafe_allow_html=True)

# Helper function to format video duration
def format_duration(seconds):
    if not seconds:
        return "Unknown"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"

# Header UI
st.markdown('<div class="header-title">⚡ YouTube Transcript Summarizer</div>', unsafe_allow_html=True)
st.markdown('<div class="header-subtitle">Intelligent Content Summarization — Local Ollama or Gemini Cloud AI</div>', unsafe_allow_html=True)

# --- SIDEBAR CONFIGURATION ---
st.sidebar.markdown("### ⚙️ Engine Settings")

# ── Backend Selector ──────────────────────────────────────
backend = st.sidebar.radio(
    "🔧 Summarization Backend",
    options=["🏠 Local Ollama", "✨ Gemini Cloud API"],
    help="Local Ollama runs on your CPU/GPU. Gemini Cloud is faster and free (requires API key)."
)
use_gemini = backend == "✨ Gemini Cloud API"

st.sidebar.markdown("---")

# ── LOCAL OLLAMA SETTINGS ────────────────────────────────
ollama_host = "http://localhost:11434"
selected_model = "llama3.2:1b"
connected = False

if not use_gemini:
    ollama_host = st.sidebar.text_input(
        "Ollama Host URL", value="http://localhost:11434",
        help="Specify local host URL where Ollama is running."
    )
    connected = is_ollama_running(ollama_host)
    if connected:
        st.sidebar.markdown('<div class="status-badge-connected">● Ollama Connected</div>', unsafe_allow_html=True)
        models, err = get_installed_models(ollama_host)
        if err:
            st.sidebar.error(f"Error fetching models: {err}")
            models = []
    else:
        st.sidebar.markdown('<div class="status-badge-disconnected">● Ollama Offline</div>', unsafe_allow_html=True)
        st.sidebar.warning(
            "⚠️ **Ollama is not running locally!**\n\n"
            "Please follow these setup steps:\n"
            "1. Install and run **Ollama** ([ollama.com](https://ollama.com))\n"
            "2. Pull a model: `ollama pull llama3.2:1b`\n"
            "3. Refresh this page."
        )
        models = []

    if models:
        default_idx = 0
        preferred_order = ['llama3.2:1b', 'qwen2.5:0.5b', 'gemma2:2b', 'llama3.2:3b', 'llama3']
        for preferred in preferred_order:
            for idx, m in enumerate(models):
                if preferred in m.lower():
                    default_idx = idx
                    break
            else:
                continue
            break
        selected_model = st.sidebar.selectbox("🤖 Local LLM Model", options=models, index=default_idx)
    else:
        selected_model = st.sidebar.text_input(
            "Local LLM Model", value="llama3.2:1b",
            help="Input pulled model name (e.g. llama3.2:1b, gemma2:2b)"
        )

# ── GEMINI CLOUD SETTINGS ────────────────────────────────
gemini_api_key = ""
gemini_model = GEMINI_MODELS[0]
gemini_valid = False

if use_gemini:
    st.sidebar.markdown(
        "**Get a free API key:** [aistudio.google.com](https://aistudio.google.com/app/apikey)\n"
        "Free tier: 1,500 requests/day · No credit card needed"
    )
    gemini_api_key = st.sidebar.text_input(
        "🔑 Gemini API Key",
        type="password",
        placeholder="AIza...",
        help="Paste your Google AI Studio API key here."
    )

    # Dynamically fetch models if key is entered, else use fallback list
    if gemini_api_key:
        available_gemini_models, fetch_err = get_available_gemini_models(gemini_api_key)
        if fetch_err:
            st.sidebar.caption(f"⚠️ Could not fetch model list: using defaults.")
            available_gemini_models = GEMINI_MODELS
    else:
        available_gemini_models = GEMINI_MODELS

    gemini_model = st.sidebar.selectbox(
        "✨ Gemini Model",
        options=available_gemini_models,
        index=0,
        help="gemini-3.1-flash is fastest. gemini-3.5-flash is highest quality."
    )

    if gemini_api_key:
        if st.sidebar.button("🔍 Validate API Key"):
            with st.sidebar:
                with st.spinner("Validating..."):
                    ok, err = validate_gemini_api_key(gemini_api_key)
                if ok:
                    st.sidebar.success("✅ API key is valid!")
                    gemini_valid = True
                else:
                    st.sidebar.error(f"❌ {err}")
        else:
            # Assume valid if key is entered (validated on submit)
            gemini_valid = True
    else:
        st.sidebar.info("👆 Enter your Gemini API key to enable cloud summarization.")

# Summary Settings
detail_level = st.sidebar.select_slider("Detail Level", options=["Short", "Medium", "Long"], value="Medium")

st.sidebar.markdown("---")
if use_gemini:
    st.sidebar.markdown(
        "☁️ **Gemini Cloud Mode**\n"
        "Transcript text is sent to Google's Gemini API. Summary is generated in the cloud."
    )
else:
    st.sidebar.markdown(
        "💬 **Local & Private Mode**\n"
        "Processing runs 100% on your machine via Ollama. Nothing is sent to the cloud."
    )

# --- MAIN PAGE WORKFLOW ---

# Initializing Session State variables
if 'metadata' not in st.session_state:
    st.session_state.metadata = None
if 'transcript' not in st.session_state:
    st.session_state.transcript = None
if 'summary' not in st.session_state:
    st.session_state.summary = None
if 'stats' not in st.session_state:
    st.session_state.stats = {}

# URL Input Bar
youtube_url = st.text_input(
    "🔗 Enter YouTube Video URL:", 
    placeholder="https://www.youtube.com/watch?v=...",
    help="Support URLs including youtu.be, youtube.com/watch, etc."
)

# Summarization Trigger Button
cols_btn = st.columns([1, 4])
with cols_btn[0]:
    start_summarize = st.button("⚡ Summarize Video", use_container_width=True)

if start_summarize:
    if not youtube_url:
        st.error("Please enter a valid YouTube URL.")
    elif use_gemini and not gemini_api_key:
        st.error("Please enter your Gemini API key in the sidebar to use cloud summarization.")
    elif not use_gemini and not connected:
        st.error("Cannot summarize. Ollama local server is offline! Please start Ollama first.")
    else:
        st.session_state.metadata = None
        st.session_state.transcript = None
        st.session_state.summary = None
        st.session_state.stats = {}
        
        # Step-by-step Execution Status Box
        with st.status("🚀 Initializing Pipeline...", expanded=True) as status_box:
            
            # --- STAGE 1: METADATA EXTRACTION ---
            status_box.update(label="🔍 Stage 1/3: Extracting video metadata...", state="running")
            start_time = time.time()
            metadata, err = get_video_metadata(youtube_url)
            if err:
                status_box.update(label="❌ Failed to retrieve video metadata", state="error")
                st.error(err)
            else:
                st.session_state.metadata = metadata
                
                # --- STAGE 2: TRANSCRIPT EXTRACTION ---
                status_box.update(label="📜 Stage 2/3: Retrieving video transcript...", state="running")
                ext_start = time.time()
                transcript, err = get_transcript(youtube_url)
                ext_end = time.time()
                
                if err:
                    status_box.update(label="❌ Failed to retrieve transcript", state="error")
                    st.error(f"Error: {err}\n\nPlease check if this video has English subtitles/captions enabled.")
                else:
                    st.session_state.transcript = transcript
                    st.session_state.stats['extract_time'] = round(ext_end - ext_start, 2)
                    st.session_state.stats['transcript_words'] = len(transcript.split())
                    
                    # --- STAGE 3: SUMMARIZATION ---
                    if use_gemini:
                        status_box.update(label="✨ Stage 3/3: Running Gemini Cloud summarization...", state="running")
                    else:
                        status_box.update(label="🧠 Stage 3/3: Running local LLM summarization...", state="running")

                    sum_start = time.time()

                    # Route to the correct backend
                    if use_gemini:
                        summary_generator = generate_final_summary_gemini(
                            transcript=st.session_state.transcript,
                            api_key=gemini_api_key,
                            model_name=gemini_model,
                            detail_level=detail_level
                        )
                    else:
                        summary_generator = generate_final_summary(
                            transcript=st.session_state.transcript,
                            model=selected_model,
                            host=ollama_host,
                            detail_level=detail_level
                        )

                    summary_text = ""
                    # Create a placeholder in the main UI to render streaming output live
                    live_summary_title = st.subheader("📝 Live Summary Generation:")
                    live_summary_box = st.empty()

                    for step in summary_generator:
                        if "error" in step:
                            status_box.update(label="❌ Summarization failed", state="error")
                            st.error(step["error"])
                            break
                        elif "summary" in step:
                            summary_text = step["summary"]
                        elif "summary_so_far" in step:
                            summary_text = step["summary_so_far"]
                            # Update the live placeholder with the generated markdown text
                            live_summary_box.markdown(summary_text)
                        else:
                            # Update sub-status message
                            status_box.update(label=f"🧠 Stage 3/3: {step['status']}", state="running")
                            
                    # Clean up the live display title once finished
                    live_summary_title.empty()
                    live_summary_box.empty()
                    
                    sum_end = time.time()
                    
                    if summary_text:
                        st.session_state.summary = summary_text
                        st.session_state.stats['summarize_time'] = round(sum_end - sum_start, 2)
                        st.session_state.stats['summary_words'] = len(summary_text.split())
                        st.session_state.stats['total_time'] = round(sum_end - start_time, 2)
                        
                        status_box.update(label="✅ Summarization completed successfully!", state="complete")

# --- OUTPUT DISPLAY SECTION ---
if st.session_state.summary and st.session_state.metadata:
    # 1. Show Video Metadata Card
    meta = st.session_state.metadata
    st.markdown(f"""
    <div class="video-card">
        <img class="video-thumb" src="{meta['thumbnail']}" alt="Thumbnail">
        <div class="video-details">
            <div class="video-title">{meta['title']}</div>
            <div class="video-channel">👤 {meta['channel']}</div>
            <div class="video-meta-pills">
                <div class="video-pill">⏱️ Duration: {format_duration(meta['duration'])}</div>
                <div class="video-pill">👁️ Views: {meta['view_count']:,}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. Render Tabs
    tab_summary, tab_transcript, tab_stats = st.tabs(["📝 Summary", "📜 Full Transcript", "📊 Stats & Diagnostics"])
    
    with tab_summary:
        st.markdown(st.session_state.summary)
        
        # Download summary button
        st.download_button(
            label="💾 Download Summary (Markdown)",
            data=st.session_state.summary,
            file_name=f"Summary_{meta['title'].replace(' ', '_')[:30]}.md",
            mime="text/markdown"
        )
        
    with tab_transcript:
        st.markdown("Here is the complete text retrieved from subtitles/captions:")
        st.text_area(
            label="Raw Transcript", 
            value=st.session_state.transcript, 
            height=350, 
            disabled=False,
            label_visibility="collapsed"
        )
        
        st.download_button(
            label="💾 Download Raw Transcript (Text)",
            data=st.session_state.transcript,
            file_name=f"Transcript_{meta['title'].replace(' ', '_')[:30]}.txt",
            mime="text/plain"
        )
        
    with tab_stats:
        st.markdown("### 📊 Performance & Optimization Analytics")
        
        # Calculate ratio
        t_words = st.session_state.stats.get('transcript_words', 0)
        s_words = st.session_state.stats.get('summary_words', 0)
        reduction = round((1 - (s_words / max(t_words, 1))) * 100, 1)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-val">{t_words:,}</div>
                <div class="stat-label">Transcript Word Count</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-val">{s_words:,}</div>
                <div class="stat-label">Summary Word Count</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-val">{reduction}%</div>
                <div class="stat-label">Reading Time Saved</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-val">{st.session_state.stats.get('total_time', 0)}s</div>
                <div class="stat-label">Total Processing Time</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("#### Detail Breakdown")
        st.write(f"- **Subtitle Fetching Time**: `{st.session_state.stats.get('extract_time', 0)}s` (via local cache / quick HTTP request)")
        if use_gemini:
            st.write(f"- **LLM Summarization Inference Time**: `{st.session_state.stats.get('summarize_time', 0)}s` (using Gemini Cloud Model `{gemini_model}`)")
            st.write(f"- **Cloud Processing Rate**: `{round(t_words / max(st.session_state.stats.get('summarize_time', 1), 1), 1)} words/second` (single-pass Gemini API inference)")
        else:
            st.write(f"- **LLM Summarization Inference Time**: `{st.session_state.stats.get('summarize_time', 0)}s` (using local Model `{selected_model}` via Ollama)")
            st.write(f"- **Hardware Processing Rate**: `{round(t_words / max(st.session_state.stats.get('summarize_time', 1), 1), 1)} words/second` (includes chunking, parsing, and multi-stage map-reduce synthesis)")
