"""Entry point + the "conversational shopping assistant" workflow.

Run with the FastAPI backend already up:

    uvicorn app.api.main:app --reload
    streamlit run app/ui/streamlit_app.py

The other 4 required workflows (recommendations, comparison, review
summaries, policy/FAQ) are Streamlit's auto-discovered ``pages/`` — this
file is deliberately the most general one: a free-text chat that lets the
coordinator itself classify and route, per spec Section 4.
"""

import streamlit as st

from app.ui.client import SmartshopAPIError, get_client
from app.ui.components import render_coordinator_response

st.set_page_config(page_title="Smartshop Assistant", page_icon="🛍️", layout="wide")

with st.sidebar:
    st.subheader("🛍️ Smartshop")
    st.caption("Conversational shopping assistant")
    try:
        get_client().health()
        st.success("API connected")
    except SmartshopAPIError as error:
        st.error(str(error))

st.title("💬 Conversational Shopping Assistant")
st.caption(
    "Ask about product recommendations, comparisons, reviews, or store policies — "
    "the coordinator classifies your question and routes it automatically."
)

# Client-side transcript only, for display continuity — each turn below still
# calls the stateless handle_query() with no prior-turn context. This is a
# UI convenience, not agent memory (spec Section 5 marks multi-turn memory
# out of scope; nothing here changes that).
st.session_state.setdefault("messages", [])

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        else:
            render_coordinator_response(message["response"])

if user_query := st.chat_input("What are you looking for?"):
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.write(user_query)

    with st.chat_message("assistant"):
        try:
            response = get_client().query(user_query)
        except SmartshopAPIError as error:
            st.error(str(error))
        else:
            render_coordinator_response(response)
            st.session_state.messages.append({"role": "assistant", "response": response})
