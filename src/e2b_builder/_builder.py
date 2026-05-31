from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from e2b import AsyncSandbox, AsyncTemplate
from e2b.api.client.api.templates import delete_templates_template_id
from e2b.sandbox_async.sandbox_api import get_api_client
from e2b.connection_config import ConnectionConfig

from e2b_builder.errors import BuildError, ContextNotFoundError, DockerfileNotFoundError
from e2b_builder.models import BuildResult


async def build(
    dockerfile: Path | str,
    context: Path | str | None = None,
    *,
    name: str = "unnamed",
    cpu_count: int = 2,
    memory_mb: int = 1024,
    api_key: str = "",
    on_log: Callable[[str], None] | None = None,
) -> BuildResult:
    dockerfile_path = Path(dockerfile)
    if not dockerfile_path.exists():
        raise DockerfileNotFoundError(dockerfile_path)

    context_path = Path(context) if context is not None else dockerfile_path.parent
    if not context_path.exists():
        raise ContextNotFoundError(context_path)

    template = AsyncTemplate(file_context_path=str(context_path))
    template = template.from_dockerfile(dockerfile_path.read_text())

    def _on_build_logs(log) -> None:
        if on_log is not None:
            on_log(log.message)

    try:
        info = await AsyncTemplate.build(
            template,
            name=name,
            cpu_count=cpu_count,
            memory_mb=memory_mb,
            on_build_logs=_on_build_logs,
            api_key=api_key,
        )
    except Exception as exc:
        raise BuildError(str(exc)) from exc

    return BuildResult(template_id=info.template_id, name=name)


async def delete(template_id: str, *, api_key: str = "") -> bool:
    """Delete a template by ID. Returns True if deleted, False if not found."""
    config = ConnectionConfig(api_key=api_key)
    api_client = get_api_client(config)
    res = await delete_templates_template_id.asyncio_detailed(
        template_id, client=api_client
    )
    if res.status_code == 404:
        return False
    if res.status_code >= 300:
        raise BuildError(f"Failed to delete template {template_id}: {res.status_code}")
    return True
