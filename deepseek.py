import streamlit as st
from openai import OpenAI
import base64
import mimetypes
import os
import uuid
import json
from datetime import datetime

st.set_page_config(page_title="Ooumph", page_icon="👑", layout="wide")

AZURE_ENDPOINT = "https://ai-praveenmishraai8491456994967768.services.ai.azure.com/models"
AZURE_API_KEY = "Fq04ZUOnjv0YpY39JUp9YZ922aZqTpc7glsIpbBl2Ki11ZIAmb0qJQQJ99CEACYeBjFXJ3w3AAAAACOGQ9Nb"
HISTORY_FILE = "chat_history.json"

@st.cache_resource
def get_client():
            return OpenAI(base_url=AZURE_ENDPOINT, api_key=AZURE_API_KEY)

@st.cache_data(ttl=60)
def load_allowed_emails(path="allowed_emails.csv"):
            if not os.path.exists(path):
                            return set()
                        emails = set()
    with open(path, "r") as f:
                    for i, line in enumerate(f):
                                        line = line.strip()
                                        if i == 0 and line.lower() == "email":
                                                                continue
                                                            if line:
                                                                                    emails.add(line.lower())
                                                                        return emails

def load_history():
            if os.path.exists(HISTORY_FILE):
                            try:
                                                with open(HISTORY_FILE, "r") as f:
                                                                        return json.load(f)
                            except Exception:
                                                pass
                                        return {}

def save_history(history):
            try:
                            with open(HISTORY_FILE, "w") as f:
                                                json.dump(history, f)
except Exception:
        pass

def file_to_content_part(uploaded_file):
            file_bytes = uploaded_file.read()
    mime_type = (
                    uploaded_file.type
                    or mimetypes.guess_type(uploaded_file.name)[0]
                    or "application/octet-stream"
    )
    b64 = base64.b64encode(file_bytes).decode()
    if mime_type.startswith("image/"):
                    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
    return {
                    "type": "text",
                    "text": f"[File: {uploaded_file.name} ({mime_type})]\n{file_bytes.decode('utf-8', errors='replace')}"
    }

def render_message(msg):
            content = msg["content"]
    if isinstance(content, str):
                    st.markdown(content)
elif isinstance(content, list):
        for part in content:
                            if part.get("type") == "text":
                                                    st.markdown(part["text"])
elif part.get("type") == "image_url":
                url = part["image_url"]["url"]
                if url.startswith("data:image/"):
                                            st.image(url)

def show_login():
            _, col, _ = st.columns([1, 1.4, 1])
    with col:
                    st.markdown("""
                    <style>
                    header,footer{visibility:hidden}
                    .lcard{background:linear-gradient(135deg,#0f0f0f,#1a1a2e);border:1px solid #2a2a4a;
                    border-radius:16px;padding:2.5rem 2rem;box-shadow:0 8px 40px rgba(0,0,0,.6);margin-top:8vh}
                    .ltitle{font-size:2rem;font-weight:800;text-align:center;
                    background:linear-gradient(90deg,#a78bfa,#60a5fa);-webkit-background-clip:text;
                    -webkit-text-fill-color:transparent;margin-bottom:.25rem}
                    .lsub{text-align:center;color:#6b7280;font-size:.85rem;margin-bottom:1.8rem}
                    </style>
                    <div class="lcard">
                    <div class="ltitle">👑 Ooumph</div>
                    <div class="lsub">Enter your authorised email to continue</div>
                    </div>""", unsafe_allow_html=True)
        with st.form("login_form"):
                            email = st.text_input("Email", placeholder="you@company.ai", label_visibility="collapsed")
            if st.form_submit_button("Continue →", use_container_width=True):
                                    if not email.strip():
                                                                st.warning("Please enter your email.")
            elif email.strip().lower() in load_allowed_emails():
                    st.session_state["authenticated"] = True
                    st.session_state["user_email"] = email.strip().lower()
                    st.rerun()
else:
                    st.error("Access denied. Your email is not on the approved list.")

def show_chat():
            if "messages" not in st.session_state:
                            st.session_state["messages"] = []
    if "chat_id" not in st.session_state:
                    st.session_state["chat_id"] = str(uuid.uuid4())[:8]
        st.session_state["chat_title"] = f"Chat {datetime.now().strftime('%b %d %H:%M')}"
    if "all_history" not in st.session_state:
                    st.session_state["all_history"] = load_history()

    with st.sidebar:
                    st.markdown(f"**👤 {st.session_state.get('user_email', '')}**")
        if st.button("🚪 Logout", use_container_width=True):
                            for k in ["authenticated", "user_email", "messages", "chat_id", "chat_title"]:
                                                    st.session_state.pop(k, None)
                                                st.rerun()

        st.markdown("---")
        st.markdown("## ⚙️ Settings")
        st.session_state["model"] = st.selectbox(
                            "Model", ["DeepSeek-V3", "DeepSeek-V4-Flash", "Kimi-K2.6"], index=1
        )
        st.session_state["temperature"] = st.slider("Temperature", 0.0, 2.0, 0.7, 0.05)
        st.session_state["max_tokens"] = int(st.number_input("Max tokens", 256, 32000, 4096, 256))

        st.markdown("---")
        uploads = st.file_uploader("Attach file/image", accept_multiple_files=True, type=None)
        st.session_state["uploads"] = uploads or []

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
                            if st.button("➕ New Chat", use_container_width=True):
                                                    if st.session_state["messages"]:
                                                                                h = st.session_state["all_history"]
                                                                                h[st.session_state["chat_id"]] = {
                                                                                    "title": st.session_state["chat_title"],
                                                                                    "messages": st.session_state["messages"],
                                                                                    "ts": datetime.now().isoformat()
                                                                                }
                                                                                save_history(h)
                                                                            st.session_state["messages"] = []
                st.session_state["chat_id"] = str(uuid.uuid4())[:8]
                st.session_state["chat_title"] = f"Chat {datetime.now().strftime('%b %d %H:%M')}"
                st.rerun()
        with col2:
                            if st.button("🗑️ Clear", use_container_width=True):
                                                    st.session_state["messages"] = []
                st.rerun()

        st.markdown("---")
        st.markdown("## 🕑 Chat History")
        history = st.session_state.get("all_history", {})
        if not history:
                            st.caption("No saved chats yet.")
else:
            sorted_chats = sorted(history.items(), key=lambda x: x[1].get("ts", ""), reverse=True)
            for cid, cdata in sorted_chats:
                                    col_a, col_b = st.columns([4, 1])
                with col_a:
                                            if st.button(cdata["title"], key=f"load_{cid}", use_container_width=True):
                                                                            if st.session_state["messages"]:
                                                                                                                h = st.session_state["all_history"]
                                                                                                                h[st.session_state["chat_id"]] = {
                                                                                                                    "title": st.session_state["chat_title"],
                                                                                                                    "messages": st.session_state["messages"],
                                                                                                                    "ts": datetime.now().isoformat()
                                                                                                                        }
                                                                                                                save_history(h)
                                                                                                            st.session_state["messages"] = cdata["messages"]
                        st.session_state["chat_id"] = cid
                        st.session_state["chat_title"] = cdata["title"]
                        st.rerun()
                with col_b:
                                            if st.button("✕", key=f"del_{cid}"):
                                                                            del st.session_state["all_history"][cid]
                        save_history(st.session_state["all_history"])
                        st.rerun()

    st.title(f"👑 Ooumph — {st.session_state['chat_title']}")

    for msg in st.session_state["messages"]:
                    with st.chat_message(msg["role"]):
                                        render_message(msg)

    prompt = st.chat_input("Message Ooumph…")
    if prompt:
                    uploads = st.session_state.get("uploads", [])
        content = [{"type": "text", "text": prompt}] + [file_to_content_part(u) for u in uploads]
        user_msg = {"role": "user", "content": content if len(content) > 1 else prompt}
        st.session_state["messages"].append(user_msg)
        with st.chat_message("user"):
                            render_message(user_msg)

        client = get_client()
        with st.chat_message("assistant"):
                            placeholder = st.empty()
            full_response = ""
            stream = client.chat.completions.create(
                                    model=st.session_state.get("model", "DeepSeek-V4-Flash"),
                                    messages=st.session_state["messages"],
                                    temperature=st.session_state.get("temperature", 0.7),
                                    max_tokens=st.session_state.get("max_tokens", 4096),
                                    stream=True,
            )
            for chunk in stream:
                                    delta = chunk.choices[0].delta
                if delta and delta.content:
                                            full_response += delta.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

        st.session_state["messages"].append({"role": "assistant", "content": full_response})

        if len(st.session_state["messages"]) == 2:
                            words = prompt.split()[:5]
            st.session_state["chat_title"] = " ".join(words) + ("…" if len(prompt.split()) > 5 else "")

        h = st.session_state["all_history"]
        h[st.session_state["chat_id"]] = {
                            "title": st.session_state["chat_title"],
                            "messages": st.session_state["messages"],
                            "ts": datetime.now().isoformat()
        }
        save_history(h)

if not st.session_state.get("authenticated"):
            show_login()
else:
    show_chat()
