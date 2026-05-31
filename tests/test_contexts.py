"""Integration tests for the DEFAULT build context — no mocking, real E2B API."""
import pytest
from e2b import AsyncSandbox

from e2b_builder import build
from e2b_builder.contexts import DEFAULT


@pytest.fixture
def api_key(doppler_secrets) -> str:
    return doppler_secrets["E2B_API_KEY"]


async def test_default_context_builds_successfully(api_key, built_template):
    result = await build(dockerfile=DEFAULT.dockerfile, context=DEFAULT.context, api_key=api_key)
    await built_template(result.template_id)
    assert result.template_id


async def test_default_context_has_opencode(api_key, built_template):
    result = await build(dockerfile=DEFAULT.dockerfile, context=DEFAULT.context, api_key=api_key)
    await built_template(result.template_id)

    sandbox = await AsyncSandbox.create(result.template_id, api_key=api_key)
    try:
        r = await sandbox.commands.run("opencode --version", timeout=30)
        assert r.exit_code == 0
        assert r.stdout.strip()
    finally:
        await AsyncSandbox.kill(sandbox.sandbox_id, api_key=api_key)
