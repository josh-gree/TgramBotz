"""Shared fixtures for integration tests."""
import json
import subprocess
import pytest

from e2b_builder import delete


@pytest.fixture(scope="session")
def doppler_secrets() -> dict:
    result = subprocess.run(
        ["doppler", "secrets", "download", "--no-file", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


@pytest.fixture
async def built_template(api_key):
    """Builds a template for a test and deletes it afterwards."""
    created: list[str] = []

    async def _track(template_id: str) -> str:
        created.append(template_id)
        return template_id

    yield _track

    for tid in created:
        await delete(tid, api_key=api_key)
