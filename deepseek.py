import streamlit as st
from openai import OpenAI
import base64
import mimetypes

st.set_page_config(page_title="Ooumph", page_icon="👑", layout="wide")

AZURE_ENDPOINT = "https://ai-praveenmishraai8491456994967768.services.ai.azure.com/models"
AZURE_API_KEY = "Fq04ZUOnjv0YpY39JUp9YZ922aZqTpc7glsIpbBl2Ki11ZIAmb0qJQQJ99CEACYeBjFXJ3w3AAAAACOGQ9Nb"

@st.cache_resource
def get_client():
        return OpenAI(base_url=AZURE_ENDPOINT, api_key=AZURE_API_KEY)

def file_to_content_part(uploaded_file):
        file_bytes = uploaded_file.read()
        mime_type = uploaded_file.type or mimetypes.guess_type(uploaded_file.name)[0] or "application/octet-stream"
        b64 = base64.b64encode(file_bytes).decode()
        data_url = f"data:{mime_type};base64,{b64}"
        if mime_type.startswith("image/"):
                    return {"type": "image_url", "image_url": {"url": data_url}}
                return {"type": "text", "text": f"[File: {uploaded_file.name} ({mime_type})]\n{file_bytes.decode('utf-8', errors='replace')}"}

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

def show_sidebar():
        with st.sidebar:
                    st.markdown("## ⚙️ Settings")
                    model = st.selectbox("Model", ["DeepSeek-V3", "DeepSeek-V4-Flash", "Kimi-K2.6"], index=1)
                    st.session_state["model"] = model
                    st.session_state["temperature"] = st.slider("Temperature", 0.0, 2.0, 0.7, 0.05)
                    st.session_state["max_tokens"] = int(st.number_input("Max tokens", 256, 32000, 4096, 256))
                    st.markdown("---")
                    uploads = st.file_uploader("Attach file/image", accept_multiple_files=True, type=None)
                    st.session_state["uploads"] = uploads or []
                    st.markdown("---")
                    if st.button("🗑️ Clear conversation", use_container_width=True):
                                    st.session_state["messages"] = []
                                    st.rerun()

            def show_chat():
                    show_sidebar()
                    st.title("👑 Ooumph")

    for k, v in [("messages", []), ("model", "DeepSeek-V4-Flash"), ("temperature", 0.7), ("max_tokens", 4096)]:
                if k not in st.session_state:
                                st.session_state[k] = v

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
                                    model=st.session_state["model"],
                                    messages=st.session_state["messages"],
                                    temperature=st.session_state["temperature"],
                                    max_tokens=st.session_state["max_tokens"],
                                    stream=True,
                                )
                                for chunk in stream:
                                                    delta = chunk.choices[0].delta
                                                    if delta and delta.content:
                                                                            full_response += delta.content
                                                                            placeholder.markdown(full_response + "▌")
                                                                    placeholder.markdown(full_response)

                            st.session_state["messages"].append({"role": "assistant", "content": full_response})

show_chat()
