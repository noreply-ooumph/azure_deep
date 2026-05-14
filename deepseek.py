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
import requests

# -- Page config (must be first)
st.set_page_config(page_title="Ooumph", page_icon="👑", layout="wide")

# -- Azure AI Foundry client configuration
# Different models may require different endpoint URLs or deployment names
MODEL_CONFIGS = {
    "DeepSeek-V4-Flash": {
        "endpoint": "https://ai-praveenmishraai8491456994967768.services.ai.azure.com/models",
        "deployment": "DeepSeek-V4-Flash"
    },
    "DeepSeek-V3-0324": {
        "endpoint": "https://ai-praveenmishraai8491456994967768.services.ai.azure.com/models",
        "deployment": "DeepSeek-V3-0324"
    },
    "Kimi-K2-Instruct": {
        "endpoint": "https://ai-praveenmishraai8491456994967768.services.ai.azure.com/models",
        "deployment": "Kimi-K2-Instruct"
    }
}

AZURE_API_KEY = "Fq04ZUOnjv0YpY39JUp9YZ922aZqTpc7glsIpbBl2Ki11ZIAmb0qJQQJ99CEACYeBjFXJ3w3AAAAACOGQ9Nb"

# -- System availability flag
SYSTEM_CLOSED = False

# Cache clients per model to avoid re-initialization
@st.cache_resource
def get_client(model_name):
    try:
        config = MODEL_CONFIGS.get(model_name)
        if not config:
            return None, f"Unknown model: {model_name}"

        # For Azure OpenAI, we need to use the correct endpoint format
        # The deployment name is passed as the model parameter
        client = OpenAI(
            base_url=config["endpoint"],
            api_key=AZURE_API_KEY,
            default_headers={
                "api-key": AZURE_API_KEY
            }
        )
        return client, ""
    except Exception as e:
        return None, str(e)

def test_model_connection(model_name):
    """Test if a specific model is reachable"""
    client, error = get_client(model_name)
    if client is None:
        return False, error

    try:
        # Try a simple chat completion to test the connection
        test_response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5,
            stream=False
        )
        return True, ""
    except Exception as e:
        err_str = str(e)
        if "404" in err_str:
            return False, f"Model '{model_name}' not found at the endpoint. It may not be deployed or available."
        elif "401" in err_str or "403" in err_str:
            return False, "Authentication failed. API key may be invalid or expired."
        elif "429" in err_str:
            return False, "Rate limit exceeded for this model."
        else:
            return False, f"Connection error for '{model_name}': {err_str[:150]}"

def is_api_available():
    """Lightweight probe to check if the Azure AI endpoint is reachable."""
    if SYSTEM_CLOSED:
        return False, "The system is currently closed for maintenance."

    # Test the base endpoint
    try:
        response = requests.get(
            MODEL_CONFIGS["DeepSeek-V4-Flash"]["endpoint"],
            headers={"api-key": AZURE_API_KEY},
            timeout=5
        )
        if response.status_code == 200:
            return True, ""
        elif response.status_code == 401 or response.status_code == 403:
            return False, "API key is invalid or has expired. Contact the administrator."
        elif response.status_code == 404:
            return False, "Azure endpoint not found. The service may have been removed."
        else:
            return True, ""  # Still try to use it, might work for specific models
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Azure AI service. Check your internet connection."
    except requests.exceptions.Timeout:
        return True, ""  # Timeout might be transient, still try
    except Exception as e:
        return True, ""  # Allow through for now

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


# =============================================================================
# IMPROVED DOWNLOAD FUNCTIONALITY
# =============================================================================
def detect_code_blocks(text):
    """Detect and extract all code blocks with their language and content."""
    pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    blocks = pattern.findall(text)
    return blocks

def get_extension_for_language(lang):
    """Map language identifiers to file extensions."""
    ext_map = {
        "python":"py","py":"py","javascript":"js","js":"js","typescript":"ts","ts":"ts",
        "html":"html","css":"css","json":"json","yaml":"yaml","yml":"yml","bash":"sh","sh":"sh",
        "sql":"sql","csv":"csv","markdown":"md","md":"md","xml":"xml","toml":"toml",
        "dockerfile":"Dockerfile","r":"r","rust":"rs","go":"go","java":"java","cpp":"cpp","c":"c",
        "text":"txt","txt":"txt","plain":"txt","svg":"svg","ini":"ini","cfg":"cfg",
        "ps1":"ps1","powershell":"ps1","batch":"bat","bat":"bat",
        "diff":"diff","patch":"diff","graphql":"graphql","gql":"graphql",
        "makefile":"Makefile","cmake":"cmake","dockerfile":"Dockerfile",
    }
    return ext_map.get(lang.lower(), "txt") if lang else "txt"

def show_downloads(text, key_prefix=""):
    """Enhanced download functionality that offers files in their original format."""
    blocks = detect_code_blocks(text)
    uid = key_prefix or str(abs(hash(text)))[:8]

    with st.expander("⬇️ Download options", expanded=False):
        # --- Offer code blocks in their original format ---
        if blocks:
            st.markdown("**📦 Download individual code blocks in their original format:**")
            for idx, (lang, code) in enumerate(blocks, 1):
                ext = get_extension_for_language(lang)
                # Determine appropriate MIME type
                mime_map = {
                    "py": "text/x-python", "js": "text/javascript", "html": "text/html",
                    "css": "text/css", "json": "application/json", "csv": "text/csv",
                    "md": "text/markdown", "xml": "application/xml", "yaml": "text/yaml",
                    "yml": "text/yaml", "sh": "application/x-sh", "sql": "text/x-sql",
                    "txt": "text/plain", "svg": "image/svg+xml"
                }
                mime = mime_map.get(ext, "text/plain")

                # Create a smart filename suggestion
                code_lines = code.strip().split('\n')
                first_line = code_lines[0][:30].strip() if code_lines else f"block_{idx}"
                # Clean filename
                filename_base = re.sub(r'[^\w\s-]', '', first_line).strip().replace(' ', '_')[:20]
                if not filename_base:
                    filename_base = f"output_{idx}"

                filename = f"{filename_base}.{ext}"

                col1, col2 = st.columns([3, 1])
                with col1:
                    st.code(code[:200] + ("..." if len(code) > 200 else ""), language=lang or "text")
                with col2:
                    st.download_button(
                        label=f"📄 Download {ext.upper()}",
                        data=code.encode("utf-8"),
                        file_name=filename,
                        mime=mime,
                        key=f"dl_code_{uid}_{idx}",
                        use_container_width=True
                    )
                    st.caption(f"Size: {len(code)} chars")

        # --- Offer full response as text ---
        st.divider()
        st.markdown("**📝 Full response:**")
        st.download_button(
            label="📄 Download as .txt",
            data=text.encode("utf-8"),
            file_name="response.txt",
            mime="text/plain",
            key=f"dl_full_{uid}",
            use_container_width=True
        )

        # --- Smart format detection from user request ---
        # If the user asked for a specific file format, offer that
        if "last_user_text" in st.session_state and st.session_state["_last_user_text"]:
            user_text = st.session_state["_last_user_text"].lower()

            # Detect requested formats
            format_patterns = {
                "python": ("py", "text/x-python"),
                "javascript": ("js", "text/javascript"),
                "html": ("html", "text/html"),
                "css": ("css", "text/css"),
                "json": ("json", "application/json"),
                "csv": ("csv", "text/csv"),
                "markdown": ("md", "text/markdown"),
                "md": ("md", "text/markdown"),
                "txt": ("txt", "text/plain"),
                "text": ("txt", "text/plain"),
                "sql": ("sql", "text/x-sql"),
                "yaml": ("yaml", "text/yaml"),
                "yml": ("yml", "text/yaml"),
                "xml": ("xml", "application/xml"),
                "svg": ("svg", "image/svg+xml"),
                "bash": ("sh", "application/x-sh"),
                "sh": ("sh", "application/x-sh"),
            }

            offered_formats = set()
            for fmt_key, (ext, mime) in format_patterns.items():
                if fmt_key in user_text and ext not in offered_formats:
                    offered_formats.add(ext)

                    # Extract code block if it matches the requested format, else use full text
                    code_content = ""
                    for lang, code in blocks:
                        if get_extension_for_language(lang) == ext:
                            code_content = code
                            break

                    if not code_content:
                        code_content = text  # Fallback to full text

                    filename_base = f"output.{ext}"
                    st.download_button(
                        label=f"📄 Download as .{ext} ({fmt_key})",
                        data=code_content.encode("utf-8"),
                        file_name=filename_base,
                        mime=mime,
                        key=f"dl_requested_{uid}_{ext}",
                        use_container_width=True
                    )


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
    if "_model_status" not in st.session_state:
        st.session_state["_model_status"] = {}

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

        # Model selection with status indicator
        col_model, col_status = st.columns([3, 1])
        with col_model:
            model = st.selectbox("Model", 
                               ["DeepSeek-V4-Flash", "DeepSeek-V3-0324", "Kimi-K2-Instruct"],
                               index=["DeepSeek-V4-Flash", "DeepSeek-V3-0324", "Kimi-K2-Instruct"].index(
                                   st.session_state.selected_model
                               ) if st.session_state.selected_model in ["DeepSeek-V4-Flash", "DeepSeek-V3-0324", "Kimi-K2-Instruct"] else 0)

        # Check model availability when selected
        if model != st.session_state.selected_model:
            # Test the new model connection
            is_available, msg = test_model_connection(model)
            st.session_state["_model_status"][model] = {"available": is_available, "message": msg}

            if is_available:
                st.session_state.selected_model = model
                st.success(f"✅ {model} is available")
            else:
                st.warning(f"⚠️ {model}: {msg}")

        with col_status:
            # Show status indicator for current model
            status = st.session_state["_model_status"].get(model, {})
            if status.get("available"):
                st.markdown("🟢", help="Model available")
            else:
                st.markdown("🔴", help="Model may be unavailable")

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
                       "selected_model", "system_prompt", "_chat_saved_at", "_last_user_text", "_model_status"]:
                st.session_state.pop(key, None)
            st.rerun()

    # -- Main content area
    st.title("deepseek / kimi")

    # Get client for selected model
    client, client_error = get_client(st.session_state.selected_model)

    # System status banner
    if SYSTEM_CLOSED:
        st.warning("🔧 **System Maintenance** — The AI service is temporarily closed. The site is up but chat is disabled until service is restored.")
        client = None
    elif client is None:
        st.error(f"⚠️ **AI service unavailable** — Could not connect to the model '{st.session_state.selected_model}'. {client_error}")

    # Display current chat indicator with title
    if st.session_state.current_chat_id:
        current_title = generate_chat_title(st.session_state.messages)
        st.caption(f"💬 {current_title} | Model: {st.session_state.selected_model} | Messages: {len(st.session_state.messages)}")
    else:
        st.caption("New chat session")

    # Display messages
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            content = msg["content"]
            if msg["role"] == "user":
                clean_text = extract_text_from_content(content)
                if clean_text:
                    st.markdown(clean_text)
                if isinstance(content, list):
                    for part in content:
                        if part.get("type") == "image_url":
                            st.image(part["image_url"]["url"])
            else:
                render_message(msg)
                if isinstance(content, str):
                    # Use the enhanced download function
                    show_downloads(content, key_prefix=f"hist_{id(msg)}_{idx}")

    # File uploader
    uploaded_files = st.file_uploader(
        "Attach images, videos or files",
        accept_multiple_files=True,
        type=["png","jpg","jpeg","gif","webp","mp4","mov","avi","pdf","txt","csv","py","json"],
        label_visibility="collapsed",
        help="Upload images, videos, or documents to include with your message.",
    )

    # Chat input
    if prompt := st.chat_input("Ask anything... (attach files above)"):
        st.session_state["_last_user_text"] = prompt

        content_parts = []
        if uploaded_files:
            for uf in uploaded_files:
                content_parts.append(file_to_content_part(uf))
        content_parts.append({"type": "text", "text": prompt})
        user_content_for_api = content_parts if len(content_parts) > 1 else prompt

        st.session_state.messages.append({"role": "user", "content": user_content_for_api})

        with st.chat_message("user"):
            st.markdown(prompt)
            for uf in uploaded_files:
                if uf.type and uf.type.startswith("image/"):
                    st.image(uf)

        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in st.session_state.messages:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        st.session_state["_chat_saved_at"] = datetime.now().isoformat()

        with st.chat_message("assistant"):
            try:
                if client is None or SYSTEM_CLOSED:
                    st.warning("⚠️ AI service is unavailable right now. Please try again later.")
                    result = None
                else:
                    response = client.chat.completions.create(
                        model=st.session_state.selected_model, 
                        messages=api_messages, 
                        stream=True,
                    )
                    result = st.write_stream(
                        chunk.choices[0].delta.content or ""
                        for chunk in response if chunk.choices
                    )
            except Exception as e:
                err = str(e)
                if "404" in err:
                    st.error(f"🔌 Model '{st.session_state.selected_model}' not found at the Azure endpoint. This model may not be deployed or available.")
                    # Update model status
                    st.session_state["_model_status"][st.session_state.selected_model] = {"available": False, "message": "Model not deployed"}
                elif "401" in err or "403" in err:
                    st.error("🔑 Authentication failed — the API key may have expired. Contact the administrator.")
                elif "429" in err:
                    st.warning("⏳ Rate limit reached. Please wait a moment and try again.")
                elif "503" in err or "502" in err or "500" in err:
                    st.warning("🔧 Azure AI service is temporarily down. The site is still running — try again shortly.")
                else:
                    st.error(f"⚠️ API error: {err[:200]}")
                result = None

        if result:
            st.session_state.messages.append({"role": "assistant", "content": result})
            # Use the enhanced download function for new responses too
            show_downloads(result, key_prefix=f"new_{len(st.session_state.messages)}")

            # Auto-save chat after each message
            if not st.session_state.current_chat_id:
                st.session_state.current_chat_id = hashlib.md5(
                    f"{st.session_state['user_email']}_{datetime.now().isoformat()}".encode()
                ).hexdigest()
                st.session_state[f"chat_created_{st.session_state.current_chat_id}"] = datetime.now().isoformat()

            save_chat_history(
                st.session_state['user_email'],
                st.session_state.current_chat_id,
                st.session_state.messages,
                st.session_state.selected_model,
                system_prompt
            )
            st.session_state['_chat_saved_at'] = datetime.now().isoformat()

# -- Router
if st.session_state.get("authenticated"):
    show_app()
else:
    show_login()
