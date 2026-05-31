"""Integration tests for e2b_builder.build() — hit the real E2B API."""
import pytest
from pathlib import Path

from e2b_builder import build
from e2b_builder.models import BuildResult
from e2b_builder.errors import BuildError, ContextNotFoundError, DockerfileNotFoundError


MINIMAL_DOCKERFILE = "FROM ubuntu:22.04\nRUN echo hello\n"


# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def dockerfile(tmp_path: Path) -> Path:
    path = tmp_path / "Dockerfile"
    path.write_text(MINIMAL_DOCKERFILE)
    return path


@pytest.fixture
def api_key(doppler_secrets) -> str:
    return doppler_secrets["E2B_API_KEY"]


# ── Happy path ─────────────────────────────────────────────────────────────────


async def test_build_returns_build_result(dockerfile, api_key, built_template):
    result = await build(dockerfile=dockerfile, api_key=api_key)
    await built_template(result.template_id)
    assert isinstance(result, BuildResult)


async def test_build_result_has_non_empty_template_id(dockerfile, api_key, built_template):
    result = await build(dockerfile=dockerfile, api_key=api_key)
    await built_template(result.template_id)
    assert result.template_id
    assert isinstance(result.template_id, str)


async def test_build_result_has_correct_name(dockerfile, api_key, built_template):
    result = await build(dockerfile=dockerfile, name="test-box", api_key=api_key)
    await built_template(result.template_id)
    assert result.name == "test-box"


async def test_build_accepts_string_paths(dockerfile, api_key, built_template):
    result = await build(
        dockerfile=str(dockerfile),
        context=str(dockerfile.parent),
        api_key=api_key,
    )
    await built_template(result.template_id)
    assert isinstance(result, BuildResult)


async def test_context_defaults_to_dockerfile_parent(dockerfile, api_key, built_template):
    result = await build(dockerfile=dockerfile, api_key=api_key)
    await built_template(result.template_id)
    assert isinstance(result, BuildResult)


# ── Log streaming ──────────────────────────────────────────────────────────────


async def test_on_log_receives_build_output(dockerfile, api_key, built_template):
    logs: list[str] = []
    result = await build(dockerfile=dockerfile, api_key=api_key, on_log=logs.append)
    await built_template(result.template_id)
    assert len(logs) > 0
    assert all(isinstance(line, str) for line in logs)


async def test_build_works_without_on_log(dockerfile, api_key, built_template):
    result = await build(dockerfile=dockerfile, api_key=api_key)
    await built_template(result.template_id)
    assert result.template_id


# ── Error handling ─────────────────────────────────────────────────────────────


async def test_raises_dockerfile_not_found(tmp_path, api_key):
    with pytest.raises(DockerfileNotFoundError):
        await build(dockerfile=tmp_path / "nonexistent.Dockerfile", api_key=api_key)


async def test_raises_context_not_found(dockerfile, api_key):
    with pytest.raises(ContextNotFoundError):
        await build(
            dockerfile=dockerfile,
            context=Path("/no/such/directory"),
            api_key=api_key,
        )


async def test_raises_build_error_on_invalid_api_key(dockerfile):
    with pytest.raises(BuildError):
        await build(dockerfile=dockerfile, api_key="invalid_key_xxx")
