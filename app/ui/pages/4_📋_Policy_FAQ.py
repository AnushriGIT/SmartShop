"""Store policy / FAQ assistant."""

import streamlit as st

from app.ui.client import SmartshopAPIError, get_client
from app.ui.components import render_coordinator_response

st.title("📋 Policy / FAQ Assistant")

POLICY_TYPES = [
    "Any",
    "returns",
    "warranty",
    "shipping",
    "exchanges",
    "financing",
    "preorder",
    "price_matching",
    "repairs",
]

with st.form("policy_form"):
    policy_type = st.selectbox("Policy type (optional — leave as Any for a general question)", POLICY_TYPES)
    question = st.text_area("Your question", placeholder="What's your return policy for laptops?")
    submitted = st.form_submit_button("Ask")

if submitted:
    if not question.strip():
        st.warning("Enter a question.")
    else:
        query_text = question.strip()
        if policy_type != "Any":
            query_text = f"[{policy_type}] {query_text}"
        with st.spinner("Looking up policy..."):
            try:
                response = get_client().query(query_text)
            except SmartshopAPIError as error:
                st.error(str(error))
            else:
                render_coordinator_response(response)
