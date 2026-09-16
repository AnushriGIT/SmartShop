"""AppTest-based smoke tests: each page loads without exception, submitting
its form triggers the (mocked) client call with the expected composed
query, and the response renders. Real client calls never happen — see
conftest.py's ``fake_client_factory``.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

# AppTest.from_file resolves a relative path against the *calling* file's own
# directory, not the cwd — found by actually running this (Rule 9), not
# assumed. Build absolute paths from the project root instead.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _app_test(relative_path: str) -> AppTest:
    return AppTest.from_file(str(_PROJECT_ROOT / relative_path))


def test_main_app_loads_and_shows_health_status(fake_client_factory):
    fake_client_factory()

    at = _app_test("app/ui/streamlit_app.py")
    at.run()

    assert not at.exception
    assert at.title[0].value == "💬 Conversational Shopping Assistant"
    assert at.sidebar.success[0].value == "API connected"


def test_main_app_chat_sends_the_typed_query_and_renders_the_response(fake_client_factory):
    fake = fake_client_factory(query_response={"message": "I don't have a specialized agent for that yet."})

    at = _app_test("app/ui/streamlit_app.py")
    at.run()
    at.chat_input[0].set_value("do you sell groceries?").run()

    assert not at.exception
    assert fake.last_query == "do you sell groceries?"
    assert at.warning[0].value == "I don't have a specialized agent for that yet."


def test_main_app_chat_shows_a_friendly_error_on_api_failure(fake_client_factory):
    fake_client_factory(query_error="Can't reach the Smartshop API at http://localhost:8000.")

    at = _app_test("app/ui/streamlit_app.py")
    at.run()
    at.chat_input[0].set_value("anything").run()

    assert not at.exception
    assert "Can't reach the Smartshop API" in at.error[0].value


def test_recommendations_page_composes_the_expected_query(fake_client_factory):
    fake = fake_client_factory(query_response={"products": [], "rationale": "Nothing matched."})

    at = _app_test("app/ui/pages/1_🎯_Recommendations.py")
    at.run()
    at.selectbox[0].select("laptop").run()
    at.number_input[0].set_value(700).run()
    at.button[0].click().run()

    assert not at.exception
    assert fake.last_query == "Recommend a laptop under $700."
    assert at.info[0].value == "No products matched."


def test_compare_page_requires_at_least_two_ids(fake_client_factory):
    fake = fake_client_factory()

    at = _app_test("app/ui/pages/2_⚖️_Compare_Products.py")
    at.run()
    at.text_input[0].set_value("SP0001").run()
    at.button[0].click().run()

    assert not at.exception
    assert fake.call_count == 0
    assert "at least 2" in at.warning[0].value


def test_compare_page_composes_the_expected_query(fake_client_factory):
    fake = fake_client_factory(query_response={"products": [], "differences": ["a", "b"]})

    at = _app_test("app/ui/pages/2_⚖️_Compare_Products.py")
    at.run()
    at.text_input[0].set_value("SP0001, SP0004").run()
    at.button[0].click().run()

    assert not at.exception
    assert fake.last_query == "Compare SP0001 and SP0004."


def test_review_summaries_page_composes_the_expected_query(fake_client_factory):
    fake = fake_client_factory(
        query_response={"product_id": "SP0001", "summary": "Good.", "sentiment": "positive", "review_count": 2}
    )

    at = _app_test("app/ui/pages/3_⭐_Review_Summaries.py")
    at.run()
    at.text_input[0].set_value("SP0001").run()
    at.button[0].click().run()

    assert not at.exception
    assert fake.last_query == "What do people say about SP0001?"


def test_policy_faq_page_composes_the_expected_query_with_a_policy_type(fake_client_factory):
    fake = fake_client_factory(query_response={"policy": None, "answer": "..."})

    at = _app_test("app/ui/pages/4_📋_Policy_FAQ.py")
    at.run()
    at.selectbox[0].select("returns").run()
    at.text_area[0].set_value("laptops?").run()
    at.button[0].click().run()

    assert not at.exception
    assert fake.last_query == "[returns] laptops?"
