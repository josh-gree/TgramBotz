"""Integration tests for run() — no mocking, real E2B API."""
import pytest
from e2b_builder import build, run
from e2b_builder.models import RunResult
from e2b_builder.contexts import BuildContext
from pathlib import Path


ECHO_DOCKERFILE = "FROM ubuntu:22.04\n"


@pytest.fixture
def api_key(doppler_secrets) -> str:
    return doppler_secrets["E2B_API_KEY"]


@pytest.fixture(scope="module")
async def echo_template_id(doppler_secrets):
    """Session-scoped: build once, reuse across tests, delete at end."""
    api_key = doppler_secrets["E2B_API_KEY"]
    tmp = Path("/tmp/echo_ctx")
    tmp.mkdir(exist_ok=True)
    (tmp / "Dockerfile").write_text(ECHO_DOCKERFILE)

    ctx = BuildContext(dockerfile=tmp / "Dockerfile", context=tmp, command="cat")
    result = await build(dockerfile=ctx.dockerfile, context=ctx.context, api_key=api_key)
    yield result.template_id, ctx.command

    from e2b_builder import delete
    await delete(result.template_id, api_key=api_key)


# ── Happy path ─────────────────────────────────────────────────────────────────


async def test_run_returns_run_result(echo_template_id, api_key):
    template_id, command = echo_template_id
    result = await run(template_id, "hello world\n", command=command, api_key=api_key)
    assert isinstance(result, RunResult)


async def test_run_stdout_contains_input(echo_template_id, api_key):
    template_id, command = echo_template_id
    result = await run(template_id, "hello world\n", command=command, api_key=api_key)
    assert "hello world" in result.stdout


async def test_run_exit_code_zero_on_success(echo_template_id, api_key):
    template_id, command = echo_template_id
    result = await run(template_id, "hi\n", command=command, api_key=api_key)
    assert result.exit_code == 0


async def test_run_cleans_up_sandbox(echo_template_id, api_key):
    """No sandbox should be left running after run() returns."""
    from e2b import AsyncSandbox
    template_id, command = echo_template_id

    before = await AsyncSandbox.list(api_key=api_key).next_items()
    await run(template_id, "hi\n", command=command, api_key=api_key)
    after = await AsyncSandbox.list(api_key=api_key).next_items()

    assert len(after) <= len(before)


# ── Error handling ─────────────────────────────────────────────────────────────


async def test_run_raises_on_invalid_template(api_key):
    from e2b_builder.errors import RunError
    with pytest.raises(RunError):
        await run("nonexistent_template_id", "hi\n", command="cat", api_key=api_key)
