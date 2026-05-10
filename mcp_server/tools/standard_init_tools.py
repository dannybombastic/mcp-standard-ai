"""Tool ai_standard_init: inicializa .acm/ y vincula el workspace a un proyecto de StandarCloud."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool

from mcp_server.config import Settings
from mcp_server.storage.acm_paths import AcmPaths

logger = logging.getLogger(__name__)


def _get_environment_root(environment: str) -> str:
    """
    Retorna el directorio raíz del entorno para almacenar assets Copilot-nativos.
    
    Mapeo:
    - vscode-copilot → .github
    - claude → .claude
    - opencode → .opencode
    - unknown → .github (default)
    """
    mapping = {
        "vscode-copilot": ".github",
        "claude": ".claude",
        "opencode": ".opencode",
        "unknown": ".github",
    }
    return mapping.get(environment, ".github")


def _create_agent_template() -> str:
    """Crea la plantilla del agente de sincronización para el proyecto."""
    return """\
---
type: agent
name: MCP Sync Agent
description: Agent que enseña a usar las herramientas de sincronización MCP del proyecto
keywords: [sync, cloud, mcp, workflow]
---

# MCP Sync Agent

Soy un agente que te ayuda a sincronizar tus assets (skills, prompts, specs) entre tu workspace local y StandarCloud.

## Workflow típico

El proyecto usa StandarCloud como **fuente única de verdad** (SSOT). Los assets viven en el cloud y se proyectan localmente en tu environment root:

- **`.github/`** (VS Code/Copilot) — Documentos nativos de Copilot
- **`.claude/`** (Claude Code) — Documentos nativos de Claude
- **`.opencode/`** (OpenCode) — Documentos nativos de OpenCode

### Sincronización: nube → local (espejo)

```bash
# Ver el estado: qué hay pendiente, qué está sincronizado
ai_cloud_status

# Hacer pull (cloud → local)
# Modo espejo (default): descarga del cloud y actualiza el estado local
ai_cloud_sync

# Ver el resultado en .acm/sync-state.json
cat .acm/sync-state.json
```

### Sincronización: local → nube (push)

```bash
# Modificaste un asset local (ej: `.github/skills/my-skill.skill.md`)

# Push: subir solo este asset
ai_cloud_push slug:my-skill

# Push con preview (dry-run)
ai_cloud_push slug:my-skill dry_run:true

# Push todo lo local que cambió
ai_cloud_push type:all

# Ver qué se cambió
ai_cloud_status
```

### Sincronización bidireccional (espejo + push)

```bash
# Primero: traer cambios del cloud (pull)
ai_cloud_sync

# Luego: subir tus cambios locales (push)
ai_cloud_sync push:true

# O en una sola llamada (espejo + push automático)
ai_cloud_sync push:true
```

## Comandos principales

| Comando | Propósito |
|---------|-----------|
| `ai_cloud_status` | Reportar diferencias local vs cloud |
| `ai_cloud_sync` | Pull (espejo cloud → local) |
| `ai_cloud_sync push:true` | Pull + push bidireccional |
| `ai_cloud_push` | Push selectivo: un asset, tipo, o todo |

## Estado de sincronización

El archivo **`.acm/sync-state.json`** registra:
- `last_push`: cuándo se subió a cloud
- `last_pull`: cuándo se trajo del cloud
- `status`: "initialized", "synced", "pending", etc.

## Tips

✅ Haz pull regularmente para estar al día  
✅ Usa `dry_run: true` antes de push si dudas  
✅ Revisa `ai_cloud_status` después de cualquier cambio  
✅ Los assets locales son **referencias** del cloud, no la fuente

"""

_STANDARD_INIT_TOOLS = [
    Tool(
        name="ai_standard_init",
        description=(
            "Inicializa el workspace con el directorio .acm/ y lo vincula a un proyecto de StandarCloud. "
            "Si no se especifica project_slug, lista los proyectos disponibles y guía al usuario. "
            "Si se especifica project_slug, crea la estructura .acm/ y escribe project.json."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_slug": {
                    "type": "string",
                    "description": "Slug del proyecto en StandarCloud (ver lista con llamada sin argumentos)",
                },
                "workspace": {
                    "type": "string",
                    "description": "Ruta del workspace a inicializar (por defecto: directorio actual)",
                },
                "description": {
                    "type": "string",
                    "description": "Descripción local del workspace (opcional, no sobreescribe la del proyecto)",
                },
                "force": {
                    "type": "boolean",
                    "description": "Reinicializar aunque ya exista .acm/ (por defecto: false)",
                    "default": False,
                },
            },
            "required": [],
        },
    ),
]


async def _standard_init(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd()).resolve()
    project_slug: str | None = args.get("project_slug")
    force: bool = bool(args.get("force", False))
    local_description: str | None = args.get("description")

    # ── Sin project_slug → modo descubrimiento ─────────────────────────────
    if not project_slug:
        return await _guide_user(workspace, settings)

    # ── Con project_slug → modo inicialización ──────────────────────────────
    return await _do_init(workspace, project_slug, local_description, force, settings)


# ─────────────────────────────────────────────────────────────────────────────
# Modo descubrimiento: lista proyectos y explica qué hacer
# ─────────────────────────────────────────────────────────────────────────────

async def _guide_user(workspace: Path, settings: Settings) -> list[TextContent]:
    acm = AcmPaths(workspace)
    already_init = acm.project.exists()

    lines: list[str] = []
    lines.append("## 🚀 StandarCloud Init")
    lines.append(f"\n**Workspace:** `{workspace}`")

    if already_init:
        try:
            current = json.loads(acm.project.read_text(encoding="utf-8"))
            lines.append(
                f"\n⚠️  Ya inicializado — proyecto actual: **{current.get('project_name', current.get('project_slug', '?'))}** "
                f"(`{current.get('project_slug', '?')}`)"
            )
            lines.append("Pasa `force: true` para reinicializar.")
        except Exception:
            lines.append("\n⚠️  Ya existe `.acm/` pero `project.json` no es válido. Pasa `force: true` para reinicializar.")
    else:
        lines.append("\n`.acm/` no inicializado. Elige un proyecto y ejecuta esta tool de nuevo con `project_slug`.")

    # Intentar listar proyectos del cloud
    if not settings.token and not settings.base_url:
        lines.append(
            "\n\n> **Sin token configurado.** Configura `AI_CONTEXT_MANAGER_TOKEN` para poder listar y vincular proyectos."
        )
        lines.append(_manual_prompt())
        return [TextContent(type="text", text="\n".join(lines))]

    try:
        from mcp_server.cloud.client import CloudClient, CloudAPIError

        async with CloudClient(settings) as client:
            projects = await client.list_projects()

        if not projects:
            lines.append("\n\nNo se encontraron proyectos en tu cuenta. Crea uno en la plataforma primero.")
        else:
            lines.append("\n\n### Proyectos disponibles\n")
            lines.append("| # | Nombre | Slug | Visibilidad |")
            lines.append("|---|--------|------|-------------|")
            for i, p in enumerate(projects, 1):
                name = p.get("name", "—")
                slug = p.get("slug", "—")
                vis = p.get("config", {}).get("visibility", p.get("visibility", "—"))
                lines.append(f"| {i} | {name} | `{slug}` | {vis} |")

            lines.append(
                "\n**Siguiente paso:** llama a esta tool de nuevo con el `project_slug` del proyecto que querés vincular."
            )
            lines.append("\n```")
            lines.append(f'project_slug: "{projects[0].get("slug", "mi-proyecto")}"')
            lines.append('description: "contexto local opcional"')
            lines.append("```")

    except Exception as e:
        logger.warning("No se pudo listar proyectos: %s", e)
        lines.append(f"\n\n⚠️  No se pudo conectar al cloud: `{e}`")
        lines.append(_manual_prompt())

    return [TextContent(type="text", text="\n".join(lines))]


def _manual_prompt() -> str:
    return (
        "\n\nSi ya conocés el slug del proyecto, podés inicializar directamente:\n"
        "```\n"
        'project_slug: "tu-proyecto-slug"\n'
        "```"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Modo inicialización: crea .acm/ y escribe project.json
# ─────────────────────────────────────────────────────────────────────────────

async def _do_init(
    workspace: Path,
    project_slug: str,
    local_description: str | None,
    force: bool,
    settings: Settings,
) -> list[TextContent]:
    acm = AcmPaths(workspace)

    # ── Verificar si ya existe ──────────────────────────────────────────────
    if acm.project.exists() and not force:
        try:
            current = json.loads(acm.project.read_text(encoding="utf-8"))
            current_slug = current.get("project_slug", "?")
        except Exception:
            current_slug = "inválido"
        return [TextContent(type="text", text=(
            f"⚠️  El workspace ya está inicializado con el proyecto `{current_slug}`.\n"
            "Pasa `force: true` si querés vincularlo a un proyecto diferente."
        ))]

    # ── Validar proyecto contra cloud ───────────────────────────────────────
    project_data: dict[str, Any] = {"slug": project_slug, "name": project_slug}

    if settings.token or settings.base_url:
        try:
            from mcp_server.cloud.client import CloudClient, CloudAPIError

            async with CloudClient(settings) as client:
                remote = await client.get_project(project_slug)
                project_data = remote
        except Exception as e:
            return [TextContent(type="text", text=(
                f"❌ No se pudo verificar el proyecto `{project_slug}` en el cloud: `{e}`\n\n"
                "Verificá que el slug es correcto y que tenés acceso a ese proyecto."
            ))]
    else:
        logger.info("Sin token, aceptando project_slug sin validación remota.")

    # ── Crear estructura .acm/ ──────────────────────────────────────────────
    acm.create_all()

    # ── Detectar entorno ────────────────────────────────────────────────────
    from mcp_server.adaptors.detect import detect_environment
    environment = detect_environment()

    # ── Escribir project.json ───────────────────────────────────────────────
    project_json: dict[str, Any] = {
        "project_slug": project_data.get("slug", project_slug),
        "project_name": project_data.get("name", project_slug),
        "initialized_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "workspace": str(workspace),
    }
    if local_description:
        project_json["local_description"] = local_description
    if "description" in project_data and project_data["description"]:
        project_json["project_description"] = project_data["description"]

    acm.project.write_text(json.dumps(project_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Inicializar manifest.json si no existe ──────────────────────────────
    if not acm.manifest.exists():
        acm.manifest.write_text(
            json.dumps({"assets": [], "last_sync": None}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── Inicializar sync-state.json si no existe ────────────────────────────
    if not acm.sync_state.exists():
        acm.sync_state.write_text(
            json.dumps({"last_push": None, "last_pull": None, "status": "initialized"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── Crear agente de sincronización en el entorno ─────────────────────────
    env_root_str = _get_environment_root(environment)
    env_root = workspace / env_root_str
    agents_dir = env_root / "agents"
    agents_created = False

    try:
        agents_dir.mkdir(parents=True, exist_ok=True)
        agent_file = agents_dir / "mcp-sync.agent.md"
        
        # Solo crear si no existe o si estamos forzando reinit
        if not agent_file.exists() or force:
            agent_content = _create_agent_template()
            agent_file.write_text(agent_content, encoding="utf-8")
            agents_created = True
    except Exception as e:
        logger.warning("No se pudo crear agente de sincronización: %s", e)

    # ── Respuesta ───────────────────────────────────────────────────────────
    lines: list[str] = [
        "## ✅ Workspace inicializado",
        f"\n**Proyecto:** {project_json['project_name']} (`{project_json['project_slug']}`)",
        f"**Workspace:** `{workspace}`",
        f"**Entorno detectado:** `{environment}`",
    ]
    if local_description:
        lines.append(f"**Descripción local:** {local_description}")

    lines.append("\n### Estructura creada\n")
    lines.append("```")
    lines.append(".acm/")
    lines.append("├── project.json     ← vinculación al proyecto")
    lines.append("├── manifest.json    ← índice de assets locales")
    lines.append("└── sync-state.json  ← estado de la última sincronización")
    lines.append("```")

    if agents_created:
        lines.append(f"\n✨ **Agente de sincronización creado:**")
        lines.append(f"`{env_root_str}/agents/mcp-sync.agent.md`")
        lines.append("\nEste agente enseña cómo usar los comandos MCP para sincronizar assets.")

    lines.append("\n### Próximos pasos\n")
    lines.append("1. **Sincronizar contexto:** `ai_sync_environment_docs` → materializa los documentos del proyecto")
    lines.append("2. **Ver estado:** `ai_cloud_status` → muestra qué hay en el cloud vs local")
    lines.append("3. **Push/Pull:** `ai_cloud_push` / `ai_cloud_pull` para sincronizar assets")

    return [TextContent(type="text", text="\n".join(lines))]
