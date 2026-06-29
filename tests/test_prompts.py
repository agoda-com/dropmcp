"""Tests for the filesystem-backed prompts provider."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from dropmcp.prompts import (
    PromptsDirectoryProvider,
    _parse_prompt_file,
    _build_prompt,
    _build_prompt_tool,
    _collect_assets,
    MAIN_FILE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_prompt(
    prompts_root: Path,
    dir_name: str,
    frontmatter: str,
    body: str = "",
) -> Path:
    """Create a prompt directory with a PROMPT.md and return its path."""
    prompt_dir = prompts_root / dir_name
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / MAIN_FILE).write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return prompt_dir


# ---------------------------------------------------------------------------
# _parse_prompt_file
# ---------------------------------------------------------------------------


def test_parse_prompt_file_basic(tmp_path):
    p = tmp_path / "PROMPT.md"
    p.write_text("---\nname: greet\ndescription: Says hi\n---\nHello {{who}}", encoding="utf-8")
    meta, body = _parse_prompt_file(p)
    assert meta["name"] == "greet"
    assert "Hello {{who}}" in body


def test_parse_prompt_file_missing_frontmatter_raises(tmp_path):
    p = tmp_path / "PROMPT.md"
    p.write_text("No frontmatter here", encoding="utf-8")
    with pytest.raises(ValueError, match="missing YAML frontmatter"):
        _parse_prompt_file(p)


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_name_and_description():
    meta = {"name": "greet", "description": "Greets someone"}
    prompt = _build_prompt(meta, "Hello!")
    assert prompt.name == "greet"
    assert "Greets" in (prompt.description or "")


def test_build_prompt_arg_substitution():
    meta = {
        "name": "greet",
        "description": "Greets",
        "arguments": [
            {"name": "who", "description": "Target", "required": True},
        ],
    }
    prompt = _build_prompt(meta, "Hello {{who}}!")
    rendered = prompt.fn(who="Alice")
    assert rendered == "Hello Alice!"


def test_build_prompt_optional_arg_defaults_to_empty():
    meta = {
        "name": "greet",
        "description": "Greets",
        "arguments": [
            {"name": "tone", "description": "Tone", "required": False},
        ],
    }
    prompt = _build_prompt(meta, "Be {{tone}} please")
    rendered = prompt.fn(tone="")
    assert rendered == "Be  please"


def test_build_prompt_multiple_args():
    meta = {
        "name": "greet",
        "description": "Greets",
        "arguments": [
            {"name": "who", "description": "Target", "required": True},
            {"name": "tone", "description": "Tone", "required": False},
        ],
    }
    prompt = _build_prompt(meta, "{{tone}} hello, {{who}}!")
    assert prompt.fn(who="Bob", tone="Warmly") == "Warmly hello, Bob!"


def test_build_prompt_no_args():
    meta = {"name": "hello", "description": "Fixed greeting"}
    prompt = _build_prompt(meta, "Hello, world!")
    assert prompt.fn() == "Hello, world!"


def test_build_prompt_tool_maps_arguments_to_input_schema():
    meta = {
        "name": "greet",
        "description": "Greets",
        "arguments": [
            {"name": "who", "description": "Target", "required": True},
            {"name": "tone", "description": "Tone", "required": False},
        ],
    }
    tool = _build_prompt_tool(_build_prompt(meta, "Hello {{who}}"))

    assert tool.name == "greet"
    assert tool.description == "Greets"
    assert tool.parameters == {
        "type": "object",
        "properties": {
            "who": {"type": "string", "description": "Target"},
            "tone": {"type": "string", "description": "Tone"},
        },
        "additionalProperties": False,
        "required": ["who"],
    }


@pytest.mark.asyncio
async def test_prompt_tool_run_returns_rendered_prompt_messages():
    meta = {
        "name": "greet",
        "description": "Greets",
        "arguments": [
            {"name": "who", "description": "Target", "required": True},
        ],
    }
    tool = _build_prompt_tool(_build_prompt(meta, "Hello {{who}}!"))

    result = await tool.run({"who": "Codex"})

    assert result.content[0].text == "Hello Codex!"
    assert result.structured_content == {
        "description": "Greets",
        "messages": [
            {
                "role": "user",
                "content": {"type": "text", "text": "Hello Codex!"},
            }
        ],
    }


# ---------------------------------------------------------------------------
# _collect_assets
# ---------------------------------------------------------------------------


def test_collect_assets_no_assets_dir(tmp_path):
    resources = _collect_assets("my-prompt", tmp_path / "assets")
    assert resources == []


def test_collect_assets_returns_resources_for_files(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "example.txt").write_text("content", encoding="utf-8")
    (assets / "data.json").write_text("{}", encoding="utf-8")

    resources = _collect_assets("my-prompt", assets)
    uris = [str(r.uri) for r in resources]
    assert any("example.txt" in u for u in uris)
    assert any("data.json" in u for u in uris)
    assert all(u.startswith("prompt://my-prompt/assets/") for u in uris)


def test_collect_assets_skips_subdirectories(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "file.md").write_text("hi", encoding="utf-8")
    (assets / "subdir").mkdir()

    resources = _collect_assets("p", assets)
    assert len(resources) == 1


# ---------------------------------------------------------------------------
# PromptsDirectoryProvider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_prompts_discovers_prompts(tmp_path):
    _write_prompt(tmp_path, "greet", "name: greet\ndescription: Says hi\n", "Hello {{who}}")
    _write_prompt(tmp_path, "farewell", "name: farewell\ndescription: Says bye\n", "Bye!")

    provider = PromptsDirectoryProvider(roots=tmp_path)
    prompts = await provider._list_prompts()

    names = {p.name for p in prompts}
    assert "greet" in names
    assert "farewell" in names


@pytest.mark.asyncio
async def test_list_tools_exposes_prompts_for_codex_originator(
    tmp_path,
    monkeypatch,
    caplog,
):
    _write_prompt(
        tmp_path,
        "greet",
        "name: greet\ndescription: Greets\narguments:\n"
        "  - name: who\n    description: Who\n    required: true\n",
        "Hello {{who}}!",
    )
    monkeypatch.setattr(
        "dropmcp.prompts.client_bucket",
        lambda: "codex_cli_rs",
    )

    provider = PromptsDirectoryProvider(roots=tmp_path)
    with caplog.at_level(logging.INFO, logger="dropmcp.prompts"):
        tools = await provider._list_tools()

    assert [tool.name for tool in tools] == ["greet"]
    assert tools[0].parameters["required"] == ["who"]
    assert "prompts_as_tools decision exposed=True client=codex_cli_rs" in caplog.text


@pytest.mark.asyncio
async def test_list_tools_exposes_prompts_for_codex_user_agent(
    tmp_path,
    monkeypatch,
):
    _write_prompt(tmp_path, "greet", "name: greet\ndescription: Greets\n")
    monkeypatch.setattr(
        "dropmcp.prompts.client_bucket",
        lambda: "codex",
    )

    provider = PromptsDirectoryProvider(roots=tmp_path)
    tools = await provider._list_tools()

    assert [tool.name for tool in tools] == ["greet"]


@pytest.mark.asyncio
async def test_list_tools_hides_prompts_for_prompt_capable_clients(
    tmp_path,
    monkeypatch,
):
    _write_prompt(tmp_path, "greet", "name: greet\ndescription: Greets\n")
    monkeypatch.setattr(
        "dropmcp.prompts.client_bucket",
        lambda: "claude-code",
    )

    provider = PromptsDirectoryProvider(roots=tmp_path)

    assert await provider._list_tools() == []
    assert [prompt.name for prompt in await provider._list_prompts()] == ["greet"]


@pytest.mark.asyncio
async def test_stateless_http_prompt_tools_are_header_scoped(tmp_path):
    import httpx
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    from dropmcp.config import Settings
    from dropmcp.server import build_server

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()
    _write_prompt(
        prompts,
        "greet",
        "name: greet\ndescription: Greets\narguments:\n"
        "  - name: who\n    description: Who\n    required: true\n",
        "Hello {{who}}!",
    )
    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        ui_enabled=False,
        feedback_enabled=False,
    )
    app = build_server(settings).http_app(stateless_http=True)

    def client_factory(headers=None, auth=None, follow_redirects=True, timeout=None):
        kwargs = {
            "transport": httpx.ASGITransport(app=app),
            "base_url": "http://testserver",
            "headers": headers,
            "follow_redirects": follow_redirects,
        }
        if auth is not None:
            kwargs["auth"] = auth
        if timeout is not None:
            kwargs["timeout"] = timeout
        return httpx.AsyncClient(**kwargs)

    codex_transport = StreamableHttpTransport(
        "http://testserver/mcp",
        headers={"originator": "codex_cli_rs"},
        httpx_client_factory=client_factory,
    )
    regular_transport = StreamableHttpTransport(
        "http://testserver/mcp",
        httpx_client_factory=client_factory,
    )

    async with app.router.lifespan_context(app):
        async with Client(codex_transport) as client:
            tools = await client.list_tools()
            prompts_list = await client.list_prompts()
            result = await client.call_tool_mcp("greet", {"who": "Codex"})

        assert [tool.name for tool in tools] == ["greet"]
        assert [prompt.name for prompt in prompts_list] == ["greet"]
        assert result.content[0].text == "Hello Codex!"

        async with Client(regular_transport) as client:
            tools = await client.list_tools()
            prompts_list = await client.list_prompts()

    assert [tool.name for tool in tools] == []
    assert [prompt.name for prompt in prompts_list] == ["greet"]


@pytest.mark.asyncio
async def test_http_prompt_tools_use_codex_client_info_without_user_agent(
    tmp_path,
    caplog,
):
    import httpx
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport
    from mcp.types import Implementation

    from dropmcp.config import Settings
    from dropmcp.server import build_server

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()
    _write_prompt(
        prompts,
        "greet",
        "name: greet\ndescription: Greets\narguments:\n"
        "  - name: who\n    description: Who\n    required: true\n",
        "Hello {{who}}!",
    )
    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        ui_enabled=False,
        feedback_enabled=False,
    )
    app = build_server(settings).http_app()

    def client_factory(headers=None, auth=None, follow_redirects=True, timeout=None):
        merged_headers = dict(headers or {})
        merged_headers["user-agent"] = ""
        kwargs = {
            "transport": httpx.ASGITransport(app=app),
            "base_url": "http://testserver",
            "headers": merged_headers,
            "follow_redirects": follow_redirects,
        }
        if auth is not None:
            kwargs["auth"] = auth
        if timeout is not None:
            kwargs["timeout"] = timeout
        return httpx.AsyncClient(**kwargs)

    transport = StreamableHttpTransport(
        "http://testserver/mcp",
        httpx_client_factory=client_factory,
    )

    async with app.router.lifespan_context(app):
        async with Client(
            transport,
            client_info=Implementation(name="codex-mcp-client", version="0.142.3"),
        ) as client:
            with caplog.at_level(logging.INFO, logger="dropmcp.prompts"):
                tools = await client.list_tools()
            prompts_list = await client.list_prompts()
            result = await client.call_tool_mcp("greet", {"who": "Codex"})

    assert [tool.name for tool in tools] == ["greet"]
    assert [prompt.name for prompt in prompts_list] == ["greet"]
    assert result.content[0].text == "Hello Codex!"
    assert "prompts_as_tools decision exposed=True client=codex" in caplog.text


@pytest.mark.asyncio
async def test_list_prompts_empty_dir(tmp_path):
    provider = PromptsDirectoryProvider(roots=tmp_path)
    prompts = await provider._list_prompts()
    assert list(prompts) == []


@pytest.mark.asyncio
async def test_list_prompts_ignores_dirs_without_prompt_md(tmp_path):
    _write_prompt(tmp_path, "valid", "name: valid\ndescription: d\n")
    (tmp_path / "no-prompt").mkdir()  # no PROMPT.md

    provider = PromptsDirectoryProvider(roots=tmp_path)
    prompts = await provider._list_prompts()
    assert len(list(prompts)) == 1


@pytest.mark.asyncio
async def test_list_prompts_skips_bad_prompt_without_crashing(tmp_path):
    _write_prompt(tmp_path, "good", "name: good\ndescription: d\n")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / MAIN_FILE).write_text("no frontmatter", encoding="utf-8")

    provider = PromptsDirectoryProvider(roots=tmp_path)
    prompts = await provider._list_prompts()
    names = {p.name for p in prompts}
    assert "good" in names
    assert "bad" not in names


@pytest.mark.asyncio
async def test_list_resources_includes_assets(tmp_path):
    prompt_dir = _write_prompt(tmp_path, "p", "name: p\ndescription: d\n")
    assets = prompt_dir / "assets"
    assets.mkdir()
    (assets / "ref.md").write_text("content", encoding="utf-8")

    provider = PromptsDirectoryProvider(roots=tmp_path)
    resources = await provider._list_resources()
    uris = [str(r.uri) for r in resources]
    assert any("ref.md" in u for u in uris)


@pytest.mark.asyncio
async def test_prompt_render_via_provider(tmp_path):
    _write_prompt(
        tmp_path,
        "greet",
        "name: greet\ndescription: Greets\narguments:\n  - name: who\n    description: Who\n    required: true\n",
        "Hello {{who}}!",
    )
    provider = PromptsDirectoryProvider(roots=tmp_path)
    prompts = await provider._list_prompts()
    greet = next(p for p in prompts if p.name == "greet")
    result = greet.fn(who="World")
    assert result == "Hello World!"
