"""Product recommendations/search — composes a natural-language query from
the form and sends it to the same POST /query every other workflow uses."""

import streamlit as st

from app.ui.client import SmartshopAPIError, get_client
from app.ui.components import render_coordinator_response

st.title("🎯 Product Recommendations")

CATEGORIES = ["Any", "laptop", "smartphone", "smart_tv", "speaker"]

with st.form("recommendation_form"):
    category = st.selectbox("Category", CATEGORIES)
    max_price = st.number_input("Max price ($)", min_value=0.0, value=0.0, step=50.0)
    details = st.text_input("Anything else you're looking for? (optional)")
    submitted = st.form_submit_button("Get Recommendations")

if submitted:
    parts = ["Recommend a"]
    parts.append(category.lower() if category != "Any" else "product")
    if max_price > 0:
        parts.append(f"under ${max_price:.0f}")
    query_text = " ".join(parts) + "."
    if details:
        query_text += f" {details}"

    with st.spinner("Finding recommendations..."):
        try:
            response = get_client().query(query_text)
        except SmartshopAPIError as error:
            st.error(str(error))
        else:
            render_coordinator_response(response)
