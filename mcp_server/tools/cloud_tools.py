"""Herramientas MCP para sincronización con StandarCloud."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_server.config import Settings
from mcp_server.storage.paths import StorageResolver
from mcp_server.storage.registry import RegistryManager
from mcp_server.storage.acm_paths import AcmPaths
from mcp_server.cloud.client import CloudClient
from mcp_server.cloud.sync import SyncManager
from mcp_server.adaptors.detect import detect_environment


def _resolve_project_slug(args: dict[str, Any], workspace: Path) -> str | None:
    if args.get("project_slug"):
        return str(args["project_slug"])
    project_file = workspace / ".acm" / "project.json"
    if project_file.exists():
        try:
            data = json.loads(project_file.read_text(encoding="utf-8"))
            slug = data.get("project_slug")
            if slug:
                return str(slug)
        except Exception:
            return None
    return None


def _collect_copilot_native_assets(workspace: Path) -> list[dict[str, Any]]:
    """Recolecta assets desde .github sin copiar nada a .acm/."""
    github_dir = workspace / ".github"
    if not github_dir.exists():
        return []

    assets: list[dict[str, Any]] = []

    instructions = github_dir / "copilot-instructions.md"
    if instructions.exists():
        assets.append(
            {
                "asset_type": "prompt",
                "slug": "copilot-instructions",
                "name": "Copilot Instructions",
                "path": ".github/copilot-instructions.md",
                "local_path": instructions,
            }
        )

    for root_markdown in sorted(github_dir.glob("*.md")):
        if root_markdown.name == "copilot-instructions.md":
            continue
        assets.append(
            {
                "asset_type": "skill",
                "slug": root_markdown.stem,
                "name": root_markdown.stem.replace("-", " ").title(),
                "path": f".github/{root_markdown.name}",
                "local_path": root_markdown,
            }
        )

    agents_dir = github_dir / "agents"
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.agent.md")):
            base = agent_file.name[:-len(".agent.md")]
            assets.append(
                {
                    "asset_type": "skill",
                    "slug": f"{base}-agent",
                    "name": f"{base.replace('-', ' ').title()} Agent",
                    "path": f".github/agents/{agent_file.name}",
                    "local_path": agent_file,
                }
            )

    skills_dir = github_dir / "skills"
    if skills_dir.exists():
        for skill_file in sorted(skills_dir.glob("*.md")):
            if skill_file.name.endswith(".skill.md"):
                base = skill_file.name[:-len(".skill.md")]
            else:
                base = skill_file.stem
            assets.append(
                {
                    "asset_type": "skill",
                    "slug": base,
                    "name": base.replace("-", " ").title(),
                    "path": f".github/skills/{skill_file.name}",
                    "local_path": skill_file,
                }
            )

    return assets


def _to_sync_state_key(asset_type: str, path: str) -> str:
    normalized_path = path
    if normalized_path.startswith(".github/"):
        normalized_path = normalized_path[len(".github/"):]

    if normalized_path.startswith("agents/"):
        return normalized_path
    if normalized_path == "copilot-instructions.md":
        return f"prompt/{normalized_path}"
    if normalized_path.startswith("skills/"):
        skill_path = normalized_path[len("skills/"):]
        return f"skill/{skill_path}"

    return f"{asset_type}/{normalized_path}"


def _write_sync_state(workspace: Path, stage: str, payload: dict[str, Any]) -> None:
    acm = AcmPaths(workspace)
    acm.create_all()
    body = {
        "version": 1,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        "stage": stage,
        "project_root": str(workspace.resolve()),
        "payload": payload,
    }
    acm.sync_state.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")


async def _push_copilot_native_assets(
    workspace: Path,
    settings: Settings,
    project_slug: str,
    filter_type: str,
    filter_slug: str | None,
) -> list[dict[str, Any]]:
    assets = _collect_copilot_native_assets(workspace)
    if not assets:
        return []

    if filter_type != "all":
        assets = [a for a in assets if a["asset_type"] == filter_type]
    if filter_slug:
        assets = [a for a in assets if a["slug"] == filter_slug]

    async with CloudClient(settings=settings) as client:
        remote_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for t in ("skill", "prompt", "spec"):
            remote_assets = await client.list_assets(t, project_slug=project_slug)
            for remote in remote_assets:
                key = (t, str(remote.get("path", "")))
                remote_by_key[key] = remote

        results: list[dict[str, Any]] = []
        for asset in assets:
            key = (asset["asset_type"], asset["path"])
            existing = remote_by_key.get(key)
            local_content = asset["local_path"].read_text(encoding="utf-8")

            if existing and str(existing.get("content", "")) == local_content:
                results.append(
                    {
                        "slug": asset["slug"],
                        "type": asset["asset_type"],
                        "action": "skip",
                        "status": "no_changes",
                        "cloud_id": existing.get("id"),
                        "path": asset["path"],
                    }
                )
                continue

            cloud_id = str(existing.get("id")) if existing else None
            result = await client.push_asset_content(
                local_path=asset["local_path"],
                asset_type=asset["asset_type"],
                project_slug=project_slug,
                asset_path=asset["path"],
                name=asset["name"],
                cloud_id=cloud_id,
            )
            results.append(
                {
                    "slug": asset["slug"],
                    "type": asset["asset_type"],
                    "action": "update" if cloud_id else "create",
                    "status": "ok",
                    "cloud_id": result.get("id"),
                    "path": asset["path"],
                }
            )
        return results


async def _pull_copilot_native_assets(
    workspace: Path,
    settings: Settings,
    project_slug: str,
    filter_type: str,
    filter_slug: str | None,
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Restaura assets cloud en estructura .github para entorno Copilot."""
    async with CloudClient(settings=settings) as client:
        remote_assets: list[dict[str, Any]] = []
        for t in ("skill", "prompt", "spec"):
            remote_assets.extend(await client.list_assets(t, project_slug=project_slug))

        if filter_type != "all":
            remote_assets = [a for a in remote_assets if a.get("asset_type") == filter_type]
        if filter_slug:
            remote_assets = [
                a for a in remote_assets if Path(str(a.get("path", ""))).stem == filter_slug
            ]

        results: list[dict[str, Any]] = []
        for asset in remote_assets:
            asset_type = str(asset.get("asset_type", ""))
            remote_path = str(asset.get("path", ""))
            cloud_id = str(asset.get("id", ""))
            if not remote_path or not cloud_id:
                continue

            # Solo restauramos configuración Copilot desde .github/
            if not remote_path.startswith(".github/"):
                continue

            target_path = workspace / remote_path
            if dry_run:
                results.append(
                    {
                        "slug": Path(remote_path).stem,
                        "type": asset_type,
                        "action": "update" if target_path.exists() else "create",
                        "status": "dry_run",
                        "path": remote_path,
                    }
                )
                continue

            existed = target_path.exists()
            fetched = await client.pull_asset_content(cloud_id, target_path)
            results.append(
                {
                    "slug": Path(remote_path).stem,
                    "type": asset_type,
                    "action": "update" if existed else "create",
                    "status": "ok",
                    "path": remote_path,
                    "cloud_id": cloud_id,
                    "updated_at": fetched.get("updated_at"),
                }
            )

        return results


def register_cloud_tools(server: Server, settings: Settings) -> None:

    @server.list_tools()
    async def _list() -> list[Tool]:
        return _CLOUD_TOOLS

    @server.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        handlers = {
            "ai_cloud_push": _cloud_push,
            "ai_cloud_pull": _cloud_pull,
            "ai_cloud_sync": _cloud_sync,
            "ai_cloud_status": _cloud_status,
        }
        if name in handlers:
            return await handlers[name](arguments, settings)
        raise ValueError(f"Tool desconocida: {name}")


_CLOUD_TOOLS = [
    Tool(
        name="ai_cloud_push",
        description="Publica assets locales en StandarCloud. Sube skills, prompts y specs al servidor.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skill", "prompt", "spec", "all"], "default": "all"},
                "slug": {"type": "string", "description": "Si se especifica, sube solo este asset"},
                "project_slug": {"type": "string", "description": "Slug del proyecto cloud (opcional si existe .acm/project.json)"},
                "workspace": {"type": "string"},
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_cloud_pull",
        description="DEPRECATED: Descarga assets. Usa cloud API directamente para gestionar contexto.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skill", "prompt", "spec", "all"], "default": "all"},
                "slug": {"type": "string", "description": "Si se especifica, descarga solo este asset"},
                "workspace": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
                "mirror_delete": {
                    "type": "boolean",
                    "default": False,
                    "description": "Modo espejo: borra en local lo que ya no exista en cloud.",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "Si True, muestra qué se haría sin ejecutar.",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_cloud_sync",
        description="Sincroniza cloud → workspace en modo espejo (por defecto). Opcionalmente permite push local → cloud.",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "dry_run": {"type": "boolean", "default": False, "description": "Si True, muestra qué se haría sin ejecutar"},
                "push": {"type": "boolean", "default": False, "description": "Si True, también hace push de cambios locales antes del pull espejo."},
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_cloud_status",
        description="Muestra el estado de sincronización: assets locales vs remotos, pendientes de push/pull.",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
            },
            "required": [],
        },
    ),
]


def _make_sync(settings: Settings, paths, registry: RegistryManager) -> SyncManager:
    client = CloudClient(settings=settings)
    return SyncManager(paths=paths, registry=registry, client=client)


async def _cloud_push(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    workspace = Path(args.get("workspace") or Path.cwd())
    project_slug = _resolve_project_slug(args, workspace)
    if not project_slug:
        return [TextContent(type="text", text=json.dumps({"error": "project_slug es requerido para push"}, ensure_ascii=False))]

    filter_type = args.get("type", "all")
    filter_slug = args.get("slug")

    if detect_environment() == "vscode-copilot":
        native_result = await _push_copilot_native_assets(
            workspace=workspace,
            settings=settings,
            project_slug=project_slug,
            filter_type=filter_type,
            filter_slug=filter_slug,
        )
        return [TextContent(type="text", text=json.dumps(native_result, indent=2, ensure_ascii=False))]

    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)
    registry.load()

    sync = _make_sync(settings, paths, registry)

    if filter_slug and filter_type != "all":
        result = [await sync.push_asset(filter_type, filter_slug, project_slug=project_slug)]
    else:
        result = await sync.push_all(project_slug=project_slug)

    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]


async def _cloud_pull(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    workspace = Path(args.get("workspace") or Path.cwd())
    project_slug = _resolve_project_slug(args, workspace)
    if not project_slug:
        return [TextContent(type="text", text=json.dumps({"error": "project_slug es requerido para pull"}, ensure_ascii=False))]

    filter_type = args.get("type", "all")
    filter_slug = args.get("slug")
    dry_run = bool(args.get("dry_run", False))

    if detect_environment() == "vscode-copilot":
        native_result = await _pull_copilot_native_assets(
            workspace=workspace,
            settings=settings,
            project_slug=project_slug,
            filter_type=filter_type,
            filter_slug=filter_slug,
            dry_run=dry_run,
        )
        return [TextContent(type="text", text=json.dumps(native_result, indent=2, ensure_ascii=False))]

    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)
    registry.load()

    sync = _make_sync(settings, paths, registry)
    mirror_delete = bool(args.get("mirror_delete", False))

    result = await sync.pull_all(project_slug=project_slug, dry_run=dry_run, mirror_delete=mirror_delete)
    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]


async def _cloud_sync(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    workspace = Path(args.get("workspace") or Path.cwd())
    project_slug = _resolve_project_slug(args, workspace)
    if not project_slug:
        return [TextContent(type="text", text=json.dumps({"error": "project_slug es requerido para sync"}, ensure_ascii=False))]

    environment = detect_environment()

    if environment == "vscode-copilot":
        dry_run = bool(args.get("dry_run", False))
        do_push = bool(args.get("push", False))
        push_results = []
        if do_push:
            if dry_run:
                push_results = [
                    {
                        "slug": a["slug"],
                        "type": a["asset_type"],
                        "action": "create_or_update",
                        "status": "dry_run",
                        "path": a["path"],
                    }
                    for a in _collect_copilot_native_assets(workspace)
                ]
            else:
                push_results = await _push_copilot_native_assets(
                    workspace=workspace,
                    settings=settings,
                    project_slug=project_slug,
                    filter_type="all",
                    filter_slug=None,
                )
        pull_results = await _pull_copilot_native_assets(
            workspace=workspace,
            settings=settings,
            project_slug=project_slug,
            filter_type="all",
            filter_slug=None,
            dry_run=dry_run,
        )
        result = {
            "pushed": push_results,
            "pulled": pull_results,
            "mode": "mirror_web_to_workspace",
            "push_enabled": do_push,
            "environment": environment,
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)
    registry.load()

    sync = _make_sync(settings, paths, registry)
    dry_run = args.get("dry_run", False)

    # Sync "web -> workspace" (mirror):
    # - pull_all con mirror_delete=True asegura que lo local refleje cloud
    #   (si borrás en la web, se borra local)
    # - push_all es opcional y se expone con flag para evitar subir cambios locales por accidente
    do_push = bool(args.get("push", False))

    if do_push and detect_environment() == "vscode-copilot" and project_slug and not dry_run:
        push_results = await _push_copilot_native_assets(
            workspace=workspace,
            settings=settings,
            project_slug=project_slug,
            filter_type="all",
            filter_slug=None,
        )
    else:
        push_results = await sync.push_all(project_slug=project_slug, dry_run=dry_run) if do_push else []
    pull_results = await sync.pull_all(project_slug=project_slug, dry_run=dry_run, mirror_delete=True)
    result = {"pushed": push_results, "pulled": pull_results, "mode": "mirror_web_to_workspace", "push_enabled": do_push}
    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]


async def _cloud_status(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    project_slug = _resolve_project_slug(args, workspace)
    environment = detect_environment()
    copilot_assets = _collect_copilot_native_assets(workspace)
    use_copilot_mode = environment == "vscode-copilot" or bool(copilot_assets)

    if use_copilot_mode:
        effective_environment = "vscode-copilot" if environment != "vscode-copilot" else environment
        local_assets = copilot_assets
        local_keys = {f"{a['asset_type']}|{a['path']}" for a in local_assets}

        remote_keys: set[str] = set()
        remote_map: dict[str, dict[str, Any]] = {}
        if settings.token and project_slug:
            try:
                async with CloudClient(settings=settings) as client:
                    for t in ("skill", "prompt", "spec"):
                        items = await client.list_assets(t, project_slug=project_slug)
                        for item in items:
                            p = str(item.get("path", ""))
                            if not p.startswith(".github/"):
                                continue
                            key = f"{t}|{p}"
                            remote_keys.add(key)
                            remote_map[key] = item
            except Exception as e:
                return [TextContent(type="text", text=json.dumps({
                    "cloud_configured": bool(settings.token and settings.base_url),
                    "base_url": settings.base_url,
                    "environment": effective_environment,
                    "status_error": str(e),
                }, indent=2, ensure_ascii=False))]

        synced_keys = local_keys & remote_keys
        pending_keys = local_keys - remote_keys
        only_cloud = remote_keys - local_keys

        synced_assets = []
        pending_assets = []
        for a in local_assets:
            key = f"{a['asset_type']}|{a['path']}"
            if key in synced_keys:
                synced_assets.append({
                    "type": a["asset_type"],
                    "slug": a["slug"],
                    "cloud_id": remote_map.get(key, {}).get("id"),
                    "path": a["path"],
                })
            elif key in pending_keys:
                pending_assets.append({
                    "type": a["asset_type"],
                    "slug": a["slug"],
                    "path": a["path"],
                })

        status_detail = {
            "cloud_configured": bool(settings.token and settings.base_url),
            "base_url": settings.base_url,
            "environment": effective_environment,
            "total_local": len(local_assets),
            "synced_to_cloud": len(synced_assets),
            "pending_push": len(pending_assets),
            "assets": {
                "synced": synced_assets,
                "pending": pending_assets,
            },
            "remote": {
                "local_count": len(local_keys),
                "cloud_count": len(remote_keys),
                "synced": sorted(k.replace("|", "/", 1) for k in synced_keys),
                "only_local": sorted(k.replace("|", "/", 1) for k in pending_keys),
                "only_cloud": sorted(k.replace("|", "/", 1) for k in only_cloud),
            },
        }

        sync_state_payload = {
            "local_count": len(local_keys),
            "cloud_count": len(remote_keys),
            "synced": sorted(
                _to_sync_state_key(*key.split("|", 1))
                for key in synced_keys
            ),
            "only_local": sorted(
                _to_sync_state_key(*key.split("|", 1))
                for key in pending_keys
            ),
            "only_cloud": sorted(
                _to_sync_state_key(*key.split("|", 1))
                for key in only_cloud
            ),
        }
        _write_sync_state(workspace, "status", sync_state_payload)
        return [TextContent(type="text", text=json.dumps(status_detail, indent=2, ensure_ascii=False))]

    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)
    registry.load()

    local_assets = registry.list_all()
    synced = [a for a in local_assets if a.get("cloud_id")]
    unsynced = [a for a in local_assets if not a.get("cloud_id")]

    status_detail: dict[str, Any] = {
        "cloud_configured": bool(settings.token and settings.base_url),
        "base_url": settings.base_url,
        "total_local": len(local_assets),
        "synced_to_cloud": len(synced),
        "pending_push": len(unsynced),
        "assets": {
            "synced": [{"type": a["type"], "slug": a["slug"], "cloud_id": a["cloud_id"]} for a in synced],
            "pending": [{"type": a["type"], "slug": a["slug"]} for a in unsynced],
        },
    }

    if settings.token:
        try:
            sync = _make_sync(settings, paths, registry)
            remote_status = await sync.status()
            status_detail["remote"] = remote_status
            sync_state_payload = {
                "local_count": int(remote_status.get("local_count", len(local_assets))),
                "cloud_count": int(remote_status.get("cloud_count", 0)),
                "synced": list(remote_status.get("synced", [])),
                "only_local": list(remote_status.get("only_local", [])),
                "only_cloud": list(remote_status.get("only_cloud", [])),
            }
            _write_sync_state(workspace, "status", sync_state_payload)
        except Exception as e:
            status_detail["remote_error"] = str(e)
    else:
        sync_state_payload = {
            "local_count": len(local_assets),
            "cloud_count": 0,
            "synced": [],
            "only_local": [f"{a['type']}/{a['slug']}" for a in unsynced],
            "only_cloud": [],
        }
        _write_sync_state(workspace, "status", sync_state_payload)

    return [TextContent(type="text", text=json.dumps(status_detail, indent=2, ensure_ascii=False))]
