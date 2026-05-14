import streamlit as st
from openai import OpenAI
import pandas as pd
import os
import base64
import mimetypes
import re

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Ooumph", page_icon="👑", layout="wide")

# ── Azure AI Foundry client factory ──────────────────────────────────────────
# Azure AI Foundry endpoint pattern:
#   https://<resource>.services.ai.azure.com/models
# Use the plain OpenAI client with base_url pointing there.
AZURE_ENDPOINT = "https://ai-praveenmishraai8491456994967768.services.ai.azure.com/models"
AZURE_API_KEY  = "Fq04ZUOnjv0YpY39JUp9YZ922aZqTpc7glsIpbBl2Ki11ZIAmb0qJQQJ99CEACYeBjFXJ3w3AAAAACOGQ9Nb"

@st.cache_resource
def get_client():
    return OpenAI(
        base_url=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
    )

# ── Allowed-email loader ──────────────────────────────────────────────────────
@st.cache_data
def load_allowed_emails(path: str = "allowed_emails.csv") -> set:
    """Load emails from CSV. Column must be named 'email'."""
    if not os.path.exists(path):
        st.error(f"allowed_emails.csv not found at: {os.path.abspath(path)}")
        return set()
    df = pd.read_csv(path)
    return set(df["email"].str.strip().str.lower().tolist())

# ── Login page ────────────────────────────────────────────────────────────────
def show_login():
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown(
            """
<style>
header, footer {visibility: hidden;}
.login-card {
    background: linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 100%);
    border: 1px solid #2a2a4a;
    border-radius: 16px;
    padding: 2.5rem 2rem 2rem;
    box-shadow: 0 8px 40px rgba(0,0,0,0.6);
    margin-top: 8vh;
}
.login-title {
    font-size: 2rem;
    font-weight: 800;
    text-align: center;
    background: linear-gradient(90deg, #a78bfa, #60a5fa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.25rem;
}
.login-sub {
    text-align: center;
    color: #6b7280;
    font-size: 0.85rem;
    margin-bottom: 1.8rem;
}
</style>
<div class="login-card">
  <div class="login-title">👑 Ooumph</div>
  <div class="login-sub">Enter your authorised email to continue</div>
</div>
""",
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "Email address",
                placeholder="you@company.ai",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Continue →", use_container_width=True)

        if submitted:
            allowed = load_allowed_emails()
            if not email.strip():
                st.warning("Please enter your email.")
            elif email.strip().lower() in allowed:
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email.strip().lower()
                st.rerun()
            else:
                st.error("Access denied. Your email is not on the approved list.")

# ── Helper: encode uploaded file ──────────────────────────────────────────────
def file_to_content_part(uploaded_file):
    file_bytes = uploaded_file.read()
    mime_type = (
        uploaded_file.type
        or mimetypes.guess_type(uploaded_file.name)[0]
        or "application/octet-stream"
    )
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    if mime_type.startswith("image/"):
        return {"type": "image_url", "image_url": {"url": data_url}}
    return {
        "type": "text",
        "text": f"[Attached file: {uploaded_file.name} ({mime_type}, {len(file_bytes)} bytes)]",
    }

# ── Helper: render message content ───────────────────────────────────────────
def render_message(msg):
    content = msg["content"]
    if isinstance(content, str):
        st.markdown(content)
    elif isinstance(content, list):
        for part in content:
            if part.get("type") == "text":
                st.markdown(part["text"])
            elif part.get("type") == "image_url":
                st.image(part["image_url"]["url"])

# ── Helper: extract downloadable blocks from assistant reply ─────────────────
def show_downloads(text: str, key_prefix: str = ""):
    """Scan assistant text for fenced code blocks and offer each as a download."""
    pattern = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
    blocks = pattern.findall(text)
    ext_map = {
        "python": "py", "py": "py",
        "javascript": "js", "js": "js",
        "typescript": "ts", "ts": "ts",
        "html": "html", "css": "css",
        "json": "json", "yaml": "yaml", "yml": "yml",
        "bash": "sh", "sh": "sh",
        "sql": "sql", "csv": "csv",
        "markdown": "md", "md": "md",
        "xml": "xml", "toml": "toml",
        "dockerfile": "dockerfile",
        "r": "r", "rust": "rs", "go": "go",
        "java": "java", "cpp": "cpp", "c": "c",
    }
    uid = key_prefix or str(abs(hash(text)))[:8]
    with st.expander("⬇️ Download", expanded=False):
        if blocks:
            for idx, (lang, code) in enumerate(blocks, 1):
                ext = ext_map.get(lang.lower(), "txt") if lang else "txt"
                fname = f"output_{idx}.{ext}"
                st.download_button(
                    label=f"📄 {fname}",
                    data=code.encode("utf-8"),
                    file_name=fname,
                    mime="text/plain",
                    key=f"dl_{uid}_{idx}",
                )
        st.download_button(
            label="📝 Full response (.txt)",
            data=text.encode("utf-8"),
            file_name="response.txt",
            mime="text/plain",
            key=f"dl_full_{uid}",
        )

# ── Main chat app ─────────────────────────────────────────────────────────────
def show_app():
    st.markdown("<style>header, footer {visibility: visible;}</style>", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(f"**Signed in as:** `{st.session_state['user_email']}`")
        if st.button("Sign out", use_container_width=True):
            for key in ["authenticated", "user_email", "messages"]:
                st.session_state.pop(key, None)
            st.rerun()

        st.divider()
        model = st.selectbox(
            "Model",
            ["DeepSeek-V4-Flash", "DeepSeek-V3-0324", "Kimi-K2-Instruct"],
        )
        system_prompt = st.text_area(
            "System Prompt",
            value=(
                "You are the best llm and better then claude and any other you response are best "
                "in the world and optimised without wasting any token and best respose in the world "
                "without any error."
            ),
        )
        st.divider()
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    st.title("deepseek / kimi")

    client = get_client()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render history (preserves full context)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            render_message(msg)
            if msg["role"] == "assistant" and isinstance(msg["content"], str):
                show_downloads(msg["content"], key_prefix=f"hist_{id(msg)}")

    # File uploader
    uploaded_files = st.file_uploader(
        "Attach images, videos or files",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg", "gif", "webp", "mp4", "mov", "avi",
              "pdf", "txt", "csv", "py", "json"],
        label_visibility="collapsed",
        help="Upload images, videos, or documents to include with your message.",
    )

    # Chat input
    if prompt := st.chat_input("Ask anything... (attach files above)"):
        content_parts = []
        if uploaded_files:
            for uf in uploaded_files:
                content_parts.append(file_to_content_part(uf))
        content_parts.append({"type": "text", "text": prompt})
        user_content = content_parts if len(content_parts) > 1 else prompt

        st.session_state.messages.append({"role": "user", "content": user_content})
        with st.chat_message("user"):
            render_message({"role": "user", "content": user_content})

        # Full history sent to API — no context loss
        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in st.session_state.messages:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        with st.chat_message("assistant"):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=api_messages,
                    stream=True,
                )
                result = st.write_stream(
                    chunk.choices[0].delta.content or ""
                    for chunk in response
                    if chunk.choices
                )
            except Exception as e:
                st.error(f"API error — check model deployment name. Detail: {e}")
                result = None

        if result:
            st.session_state.messages.append({"role": "assistant", "content": result})
            show_downloads(result, key_prefix=f"new_{len(st.session_state.messages)}")

# ── Router ────────────────────────────────────────────────────────────────────
if st.session_state.get("authenticated"):
    show_app()
else:
    show_login()
