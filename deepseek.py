import streamlit as st
from openai import OpenAI
import pandas as pd
import os
import base64
import mimetypes
import re
import json
from datetime import datetime
import hashlib

# -- Page config (must be first)
st.set_page_config(page_title="Ooumph", page_icon="👑", layout="wide")

# -- Azure AI Foundry client
AZURE_ENDPOINT = "https://ai-praveenmishraai8491456994967768.services.ai.azure.com/models"
AZURE_API_KEY  = "Fq04ZUOnjv0YpY39JUp9YZ922aZqTpc7glsIpbBl2Ki11ZIAmb0qJQQJ99CEACYeBjFXJ3w3AAAAACOGQ9Nb"

@st.cache_resource
def get_client():
    return OpenAI(base_url=AZURE_ENDPOINT, api_key=AZURE_API_KEY)

# -- Allowed-email loader
@st.cache_data
def load_allowed_emails(path="allowed_emails.csv"):
    if not os.path.exists(path):
        st.error(f"allowed_emails.csv not found at: {os.path.abspath(path)}")
        return set()
    df = pd.read_csv(path)
    return set(df["email"].str.strip().str.lower().tolist())

# -- Chat history management
CHAT_HISTORY_DIR = "chat_histories"
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)

def get_chat_filename(user_email, chat_id):
    safe_email = user_email.replace('@', '_at_').replace('.', '_dot_')
    return os.path.join(CHAT_HISTORY_DIR, f"{safe_email}_{chat_id}.json")

def generate_chat_title(messages):
    """Generate chat title from first user message (like Claude)"""
    for msg in messages:
        if msg["role"] == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                # Clean and truncate
                title = content.strip()[:50]
                if len(content) > 50:
                    title += "..."
                return title
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        text = part["text"].strip()[:50]
                        if len(part["text"]) > 50:
                            text += "..."
                        return text
    return "New Chat"

def save_chat_history(user_email, chat_id, messages, model, system_prompt):
    filename = get_chat_filename(user_email, chat_id)
    chat_title = generate_chat_title(messages)
    data = {
        "chat_id": chat_id,
        "user_email": user_email,
        "title": chat_title,
        "model": model,
        "system_prompt": system_prompt,
        "messages": messages,
        "updated_at": datetime.now().isoformat(),
        "created_at": getattr(st.session_state, f"chat_created_{chat_id}", datetime.now().isoformat())
    }
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def load_chat_history(user_email, chat_id):
    filename = get_chat_filename(user_email, chat_id)
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
        # Ensure backward compatibility for old chats without title
        if "title" not in data:
            data["title"] = generate_chat_title(data.get("messages", []))
        return data
    return None

def list_chat_sessions(user_email):
    sessions = []
    safe_email = user_email.replace('@', '_at_').replace('.', '_dot_')
    prefix = f"{safe_email}_"
    for fname in os.listdir(CHAT_HISTORY_DIR):
        if fname.startswith(prefix) and fname.endswith('.json'):
            chat_id = fname[len(prefix):-5]
            filepath = os.path.join(CHAT_HISTORY_DIR, fname)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                title = data.get("title")
                if not title:
                    title = generate_chat_title(data.get("messages", []))
                    data["title"] = title
                    with open(filepath, 'w') as fw:
                        json.dump(data, fw, indent=2, default=str)
                sessions.append({
                    "chat_id": chat_id,
                    "title": title,
                    "model": data.get("model", "Unknown"),
                    "created_at": data.get("created_at", "Unknown"),
                    "updated_at": data.get("updated_at", "Unknown"),
                    "message_count": len(data.get("messages", []))
                })
            except:
                continue
    return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

def delete_chat_history(user_email, chat_id):
    filename = get_chat_filename(user_email, chat_id)
    if os.path.exists(filename):
        os.remove(filename)
        return True
    return False

# -- Login page
def show_login():
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
<style>
header, footer {visibility: hidden;}
.login-card {background:linear-gradient(135deg,#0f0f0f 0%,#1a1a2e 100%);border:1px solid #2a2a4a;border-radius:16px;padding:2.5rem 2rem 2rem;box-shadow:0 8px 40px rgba(0,0,0,0.6);margin-top:8vh;}
.login-title {font-size:2rem;font-weight:800;text-align:center;background:linear-gradient(90deg,#a78bfa,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:0.25rem;}
.login-sub {text-align:center;color:#6b7280;font-size:0.85rem;margin-bottom:1.8rem;}
</style>
<div class="login-card">
  <div class="login-title">👑 Ooumph</div>
  <div class="login-sub">Enter your authorised email to continue</div>
</div>
""", unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email address", placeholder="you@company.ai", label_visibility="collapsed")
            submitted = st.form_submit_button("Continue →", use_container_width=True)

        if submitted:
            allowed = load_allowed_emails()
            if not email.strip():
                st.warning("Please enter your email.")
            elif email.strip().lower() in allowed:
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email.strip().lower()
                st.session_state["current_chat_id"] = None
                st.session_state["messages"] = []
                st.rerun()
            else:
                st.error("Access denied. Your email is not on the approved list.")

# -- Encode uploaded file
def file_to_content_part(uploaded_file):
    file_bytes = uploaded_file.read()
    mime_type = uploaded_file.type or mimetypes.guess_type(uploaded_file.name)[0] or "application/octet-stream"
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    if mime_type.startswith("image/"):
        return {"type": "image_url", "image_url": {"url": data_url}}
    return {"type": "text", "text": f"[Attached: {uploaded_file.name} ({mime_type}, {len(file_bytes)} bytes)]"}

# -- Extract clean text from message content
def extract_text_from_content(content):
    """Extract only the user's text from content, removing any code or file artifacts"""
    if isinstance(content, str):
        # Return only clean text, strip any code blocks
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if part.get("type") == "text":
                text = part["text"]
                # Only add if it's actual user text, not file attachment text
                if not text.startswith("[Attached:"):
                    text_parts.append(text)
        return "\n".join(text_parts) if text_parts else ""
    return ""

# -- Render message - FIXED to only show clean content
def render_message(msg):
    content = msg["content"]
    if isinstance(content, str):
        # Display clean text only
        st.markdown(content)
    elif isinstance(content, list):
        for part in content:
            if part.get("type") == "text":
                text = part["text"]
                # Only display if it's actual user text, not file attachment text
                if not text.startswith("[Attached:"):
                    st.markdown(text)
            elif part.get("type") == "image_url":
                st.image(part["image_url"]["url"])

# -- Download buttons for assistant reply
def show_downloads(text, key_prefix=""):
    pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    blocks = pattern.findall(text)
    ext_map = {
        "python":"py","py":"py","javascript":"js","js":"js","typescript":"ts","ts":"ts",
        "html":"html","css":"css","json":"json","yaml":"yaml","yml":"yml","bash":"sh","sh":"sh",
        "sql":"sql","csv":"csv","markdown":"md","md":"md","xml":"xml","toml":"toml",
        "dockerfile":"dockerfile","r":"r","rust":"rs","go":"go","java":"java","cpp":"cpp","c":"c"
    }
    uid = key_prefix or str(abs(hash(text)))[:8]
    with st.expander("⬇️ Download", expanded=False):
        if blocks:
            for idx, (lang, code) in enumerate(blocks, 1):
                ext = ext_map.get(lang.lower(), "txt") if lang else "txt"
                fname = f"output_{idx}.{ext}"
                st.download_button(label=f"📄 {fname}", data=code.encode("utf-8"),
                    file_name=fname, mime="text/plain", key=f"dl_{uid}_{idx}")
        st.download_button(label="📝 Full response (.txt)", data=text.encode("utf-8"),
            file_name="response.txt", mime="text/plain", key=f"dl_full_{uid}")

# -- Main app
def show_app():
    st.markdown("<style>header, footer {visibility: visible;}</style>", unsafe_allow_html=True)

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "DeepSeek-V4-Flash"
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = (
            "You are the best llm and better then claude and any other you response are best "
            "in the world and optimised without wasting any token and best respose in the world "
            "without any error."
        )
    if "_chat_saved_at" not in st.session_state:
        st.session_state["_chat_saved_at"] = ""
    if "_last_user_text" not in st.session_state:
        st.session_state["_last_user_text"] = ""

    # -- Sidebar
    with st.sidebar:
        st.markdown(f"**Signed in as:** `{st.session_state['user_email']}`")

        st.divider()
        st.markdown("### 💬 Chat Sessions")

        # New chat button
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            if st.session_state.messages and st.session_state.current_chat_id:
                save_chat_history(
                    st.session_state['user_email'],
                    st.session_state.current_chat_id,
                    st.session_state.messages,
                    st.session_state.selected_model,
                    st.session_state.system_prompt
                )
            st.session_state.messages = []
            st.session_state.current_chat_id = None
            st.session_state['_chat_saved_at'] = datetime.now().isoformat()
            st.rerun()

        # List existing chats
        sessions = list_chat_sessions(st.session_state['user_email'])

        if st.session_state.current_chat_id:
            for s in sessions:
                if s['chat_id'] == st.session_state.current_chat_id:
                    s['is_current'] = True

        if sessions:
            for session in sessions:
                is_current = session.get('is_current', False)
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    title = session.get("title", "New Chat")
                    msgs = session.get("message_count", 0)
                    button_clicked = st.button(
                        f"💬 {title} ({msgs})", 
                        key=f"chat_{session['chat_id']}_{st.session_state['_chat_saved_at']}", 
                        use_container_width=True,
                        help=f"Model: {session.get('model', 'Unknown')} | Messages: {msgs}"
                    )
                    if button_clicked:
                        data = load_chat_history(st.session_state['user_email'], session['chat_id'])
                        if data:
                            st.session_state.messages = data.get("messages", [])
                            st.session_state.current_chat_id = session['chat_id']
                            st.session_state.selected_model = data.get("model", st.session_state.selected_model)
                            st.session_state.system_prompt = data.get("system_prompt", st.session_state.system_prompt)
                            st.rerun()

                with col2:
                    if st.button("🗑️", key=f"del_{session['chat_id']}_{st.session_state['_chat_saved_at']}", help="Delete this chat"):
                        delete_chat_history(st.session_state['user_email'], session['chat_id'])
                        if st.session_state.current_chat_id == session['chat_id']:
                            st.session_state.messages = []
                            st.session_state.current_chat_id = None
                        st.rerun()

                with col3:
                    model_short = session.get('model', '?')[:6]
                    st.markdown(f"<small style='color: #6b7280;'>{model_short}</small>", unsafe_allow_html=True)
        else:
            st.info("No saved chats yet")

        st.divider()

        # Model selection
        model = st.selectbox("Model", 
                           ["DeepSeek-V4-Flash", "DeepSeek-V3-0324", "Kimi-K2-Instruct"],
                           index=["DeepSeek-V4-Flash", "DeepSeek-V3-0324", "Kimi-K2-Instruct"].index(
                               st.session_state.selected_model
                           ) if st.session_state.selected_model in ["DeepSeek-V4-Flash", "DeepSeek-V3-0324", "Kimi-K2-Instruct"] else 0)
        st.session_state.selected_model = model

        # System prompt
        system_prompt = st.text_area("System Prompt", value=st.session_state.system_prompt, height=100)
        st.session_state.system_prompt = system_prompt

        st.divider()

        # Clear current chat
        if st.button("🗑️ Clear current chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        # Sign out
        if st.button("🚪 Sign out", use_container_width=True):
            if st.session_state.messages and st.session_state.current_chat_id:
                save_chat_history(
                    st.session_state['user_email'],
                    st.session_state.current_chat_id,
                    st.session_state.messages,
                    st.session_state.selected_model,
                    st.session_state.system_prompt
                )
            for key in ["authenticated", "user_email", "messages", "current_chat_id", 
                       "selected_model", "system_prompt", "_chat_saved_at", "_last_user_text"]:
                st.session_state.pop(key, None)
            st.rerun()

    # -- Main content area
    st.title("deepseek / kimi")
    client = get_client()

    # Display current chat indicator with title
    if st.session_state.current_chat_id:
        current_title = generate_chat_title(st.session_state.messages)
        st.caption(f"💬 {current_title} | Model: {st.session_state.selected_model} | Messages: {len(st.session_state.messages)}")
    else:
        st.caption("New chat session")

    # Display messages - FIXED to only show clean user content
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            content = msg["content"]
            if msg["role"] == "user":
                # For user messages, extract and show only clean text
                clean_text = extract_text_from_content(content)
                if clean_text:
                    st.markdown(clean_text)
                # Also show images if any
                if isinstance(content, list):
                    for part in content:
                        if part.get("type") == "image_url":
                            st.image(part["image_url"]["url"])
            else:
                # For assistant messages, show as normal
                render_message(msg)
                if isinstance(content, str):
                    show_downloads(content, key_prefix=f"hist_{id(msg)}")

    # File uploader
    uploaded_files = st.file_uploader(
        "Attach images, videos or files",
        accept_multiple_files=True,
        type=["png","jpg","jpeg","gif","webp","mp4","mov","avi","pdf","txt","csv","py","json"],
        label_visibility="collapsed",
        help="Upload images, videos, or documents to include with your message.",
    )

    # Chat input - FIXED to only capture user's text
    if prompt := st.chat_input("Ask anything... (attach files above)"):
        # Store the clean user text for display
        st.session_state["_last_user_text"] = prompt

        content_parts = []
        if uploaded_files:
            for uf in uploaded_files:
                content_parts.append(file_to_content_part(uf))
        # Always add user's text as clean text part
        content_parts.append({"type": "text", "text": prompt})

        # Use the structured content for API but store clean display
        user_content_for_api = content_parts if len(content_parts) > 1 else prompt

        # Store in messages - use the structured format for API, but render only clean text
        st.session_state.messages.append({"role": "user", "content": user_content_for_api})

        # Display only clean user text immediately
        with st.chat_message("user"):
            st.markdown(prompt)
            # Also show any uploaded images
            for uf in uploaded_files:
                if uf.type and uf.type.startswith("image/"):
                    st.image(uf)

        # Prepare API messages
        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in st.session_state.messages:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        st.session_state["_chat_saved_at"] = datetime.now().isoformat()

        with st.chat_message("assistant"):
            try:
                response = client.chat.completions.create(
                    model=model, messages=api_messages, stream=True,
                )
                result = st.write_stream(
                    chunk.choices[0].delta.content or ""
                    for chunk in response if chunk.choices
                )
            except Exception as e:
                st.error(f"API error: {e}")
                result = None

        if result:
            st.session_state.messages.append({"role": "assistant", "content": result})
            show_downloads(result, key_prefix=f"new_{len(st.session_state.messages)}")

            # Auto-save chat after each message
            if not st.session_state.current_chat_id:
                st.session_state.current_chat_id = hashlib.md5(
                    f"{st.session_state['user_email']}_{datetime.now().isoformat()}".encode()
                ).hexdigest()
                st.session_state[f"chat_created_{st.session_state.current_chat_id}"] = datetime.now().isoformat()

            # Save and ensure title is set from first user message
            save_chat_history(
                st.session_state['user_email'],
                st.session_state.current_chat_id,
                st.session_state.messages,
                model,
                system_prompt
            )
            st.session_state['_chat_saved_at'] = datetime.now().isoformat()

# -- Router
if st.session_state.get("authenticated"):
    show_app()
else:
    show_login()
