import streamlit as st
from openai import AzureOpenAI
import pandas as pd
import os

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
    # Centered card via columns
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown(
            """
            <style>
            /* hide default streamlit header/footer on login */
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

# ── Main chat app ─────────────────────────────────────────────────────────────
def show_app():
    # Restore default header visibility
    st.markdown("<style>header, footer {visibility: visible;}</style>", unsafe_allow_html=True)

    # Sidebar
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

    # Azure client (created once per model selection)
    client = AzureOpenAI(
        azure_endpoint="https://ai-praveenmishraai8491456994967768.openai.azure.com/",
        api_key="Fq04ZUOnjv0YpY39JUp9YZ922aZqTpc7glsIpbBl2Ki11ZIAmb0qJQQJ99CEACYeBjFXJ3w3AAAAACOGQ9Nb",
        api_version="2024-12-01-preview",
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Input
    if prompt := st.chat_input("Ask anything..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}]
                + st.session_state.messages,
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