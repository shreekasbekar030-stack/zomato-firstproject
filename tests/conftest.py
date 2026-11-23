"""Keep model credentials out of the test process."""

import pytest


@pytest.fixture(autouse=True)
def _unset_model_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
