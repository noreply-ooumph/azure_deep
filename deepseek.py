import streamlit as st
from openai import AzureOpenAI
import pandas as pd
import os
import base64
import mimetypes

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Ooumph", page_icon="👑", layout="wide")

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

# ── Helper: encode uploaded file to base64 data URI ──────────────────────────
def file_to_content_part(uploaded_file):
    file_bytes = uploaded_file.read()
    mime_type = uploaded_file.type or mimetypes.guess_type(uploaded_file.name)[0] or "application/octet-stream"
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    if mime_type.startswith("image/"):
        return {"type": "image_url", "image_url": {"url": data_url}}
    else:
        return {"type": "text", "text": f"[Attached file: {uploaded_file.name} ({mime_type}, {len(file_bytes)} bytes)]"}

# ── Render a stored message ──────────────────────────────────────────────────
def render_message(msg):
    content = msg["content"]
    if isinstance(content, str):
        st.write(content)
    elif isinstance(content, list):
        for part in content:
            if part.get("type") == "text":
                st.write(part["text"])
            elif part.get("type") == "image_url":
                st.image(part["image_url"]["url"])
            else:
                st.write(str(part))

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
        model = st.selectbox("Model", ["DeepSeek-V4-Flash", "DeepSeek-V3.2", "Kimi-K2.6"])
        system_prompt = st.text_area(
            "System Prompt",
            value=(
                "You are the best llm and better then claude and any other you response are best "
                "in the world and optimised without wasting any token and best respose in the world "
                "without any error."
            ),
        )

    st.title("deepseek / kimi")

    client = AzureOpenAI(
        azure_endpoint="https://ai-praveenmishraai8491456994967768.openai.azure.com/",
        api_key="Fq04ZUOnjv0YpY39JUp9YZ922aZqTpc7glsIpbBl2Ki11ZIAmb0qJQQJ99CEACYeBjFXJ3w3AAAAACOGQ9Nb",
        api_version="2024-12-01-preview",
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            render_message(msg)

    uploaded_files = st.file_uploader(
        "Attach images, videos or files",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg", "gif", "webp", "mp4", "mov", "avi", "pdf", "txt", "csv", "py", "json"],
        label_visibility="collapsed",
        help="Upload images, videos, or documents to include in your message.",
    )

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

        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in st.session_state.messages:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        with st.chat_message("assistant"):
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
        st.session_state.messages.append({"role": "assistant", "content": result})

# ── Router ────────────────────────────────────────────────────────────────────
if st.session_state.get("authenticated"):
    show_app()
else:
    show_login()
