"""Fixtures for the Streamlit UI test suite (Phase 4a implementation plan).

Every test monkeypatches ``app.ui.client.get_client`` so no real HTTP call
(and therefore no real OpenAI call) ever happens — same mocking policy as
``tests/agents/`` and ``tests/api/``, just via a fake client object instead
of PydanticAI's ``TestModel`` or FastAPI's ``dependency_overrides``.
"""

import pytest

from app.ui import client as client_module
from app.ui.client import SmartshopAPIError


class FakeClient:
    """Stand-in for ``SmartshopAPIClient`` — returns a fixed response (or
    raises a fixed error) instead of making a real HTTP call."""

    def __init__(self, query_response: dict | None = None, query_error: str | None = None):
        self._query_response = query_response
        self._query_error = query_error
        self.last_query: str | None = None
        self.call_count = 0

    def health(self) -> dict:
        return {"status": "ok"}

    def query(self, text: str) -> dict:
        self.call_count += 1
        self.last_query = text
        if self._query_error is not None:
            raise SmartshopAPIError(self._query_error)
        return self._query_response


@pytest.fixture
def fake_client_factory(monkeypatch: pytest.MonkeyPatch):
    """Returns a function that installs a ``FakeClient`` as ``get_client()``'s
    result and hands back the fake instance so a test can assert on it
    (``last_query``, ``call_count``)."""

    def _install(query_response: dict | None = None, query_error: str | None = None) -> FakeClient:
        fake = FakeClient(query_response=query_response, query_error=query_error)
        monkeypatch.setattr(client_module, "get_client", lambda: fake)
        return fake

    return _install
