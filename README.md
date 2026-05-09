# AI Context Manager MCP

Servidor MCP (Model Context Protocol) en Python que actúa como **sync agent** entre el workspace local y la aplicación cloud.

## ¿Qué hace?

- Gestiona la carpeta `.ai/` en tu workspace (skills, prompts, specs, contexto, bootstrap)
- Sincroniza assets con la app cloud (`cloud_sync pull/push`)
- Genera `MODEL_BOOTSTRAP.md` adaptado al entorno (vscode, claude, opencode, cli, generic)
- Mantiene `.gitignore` actualizado para no commitear el contexto local

## Requisitos

- Python 3.11+
- pip / pipx

## Instalación

```bash
# Con pipx (recomendado, instala en entorno aislado)
pipx install .

# O con pip en un virtualenv
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
pip install -e .
```

## Variables de entorno (obligatorias para sync cloud)

```bash
# Linux/macOS
export AI_CONTEXT_MANAGER_BASE_URL="https://cloud.example.com"
export AI_CONTEXT_MANAGER_TOKEN="pat_xxx"

# Windows (PowerShell)
$env:AI_CONTEXT_MANAGER_BASE_URL="https://cloud.example.com"
$env:AI_CONTEXT_MANAGER_TOKEN="pat_xxx"

# Windows (cmd)
set AI_CONTEXT_MANAGER_BASE_URL=https://cloud.example.com
set AI_CONTEXT_MANAGER_TOKEN=pat_xxx
```

## Arrancar el servidor MCP

```bash
# Modo stdio (para clientes MCP como Claude Desktop, OpenCode, etc.)
python -m mcp_server

# O usando el script instalado
ai-context-manager serve
```

## Configuración en VS Code (tasks.json)

Crear `.vscode/tasks.json` en tu proyecto:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "AI Context Manager: Start MCP",
      "type": "shell",
      "command": "python -m mcp_server",
      "options": {
        "env": {
          "AI_CONTEXT_MANAGER_BASE_URL": "https://cloud.example.com",
          "AI_CONTEXT_MANAGER_TOKEN": "pat_xxx"
        }
      },
      "problemMatcher": []
    },
    {
      "label": "AI Context Manager: Sync (pull)",
      "type": "shell",
      "command": "ai-context-manager cloud-sync --direction pull",
      "options": {
        "env": {
          "AI_CONTEXT_MANAGER_BASE_URL": "https://cloud.example.com",
          "AI_CONTEXT_MANAGER_TOKEN": "pat_xxx"
        }
      },
      "problemMatcher": []
    }
  ]
}
```

## Configuración en Claude Desktop

Añadir en `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ai-context-manager": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "env": {
        "AI_CONTEXT_MANAGER_BASE_URL": "https://cloud.example.com",
        "AI_CONTEXT_MANAGER_TOKEN": "pat_xxx"
      }
    }
  }
}
```

## Configuración en OpenCode

Añadir en tu config de OpenCode:

```json
{
  "mcp": {
    "servers": {
      "ai-context-manager": {
        "command": "python",
        "args": ["-m", "mcp_server"],
        "env": {
          "AI_CONTEXT_MANAGER_BASE_URL": "https://cloud.example.com",
          "AI_CONTEXT_MANAGER_TOKEN": "pat_xxx"
        }
      }
    }
  }
}
```

## Setup inicial de un proyecto

```bash
# 1. Inicializar .ai/ en el workspace
ai-context-manager init --mode workspace

# 2. Vincular con proyecto cloud
ai-context-manager cloud-link --project-key my-project

# 3. Descargar assets del cloud
ai-context-manager cloud-sync --direction pull

# 4. Asegurar .gitignore
ai-context-manager ensure-gitignore
```

## Tools disponibles (MCP)

| Tool | Descripción |
|------|-------------|
| `init_storage` | Inicializa `.ai/` en workspace o global |
| `ensure_gitignore` | Añade `.ai/` al `.gitignore` |
| `scan_repo` | Escanea el repo buscando assets IA |
| `list_assets` | Lista assets (skills/prompts/specs/context) |
| `register_asset` | Registra un asset existente en el registry |
| `move_asset` | Mueve un asset actualizando el registry |
| `remove_asset` | Elimina un asset del registry |
| `create_skill` | Crea un nuevo skill desde template |
| `create_prompt` | Crea un nuevo prompt desde template |
| `create_spec` | Crea una nueva spec desde template |
| `generate_bootstrap` | Genera `MODEL_BOOTSTRAP.md` para el entorno |
| `cloud_project_link` | Vincula workspace con proyecto cloud |
| `cloud_sync` | Sincroniza assets (pull: cloud→local, push: local→cloud) |
| `cloud_pull_backup` | Descarga un backup específico del cloud |

## Resources disponibles (MCP)

| Resource | Descripción |
|----------|-------------|
| `registry://` | Contenido completo del registry.json |
| `context://bootstrap` | Contenido del MODEL_BOOTSTRAP.md |
| `skills://<id>` | Contenido de un skill por ID |
| `prompts://<id>` | Contenido de un prompt por ID |
| `specs://<id>` | Contenido de una spec por ID |

## Estructura local generada

```
.ai/
  registry.json          # fuente de verdad local
  context/
    AI_GUIDELINES.md
    MODEL_BOOTSTRAP.md   # generado por generate_bootstrap
  skills/
    *.md
  prompts/
    *.md
  specs/
    *.md
  templates/
    skill.md
    prompt.md
    spec.md
  .sync/
    state.json           # estado de sync (hashes/ETags)
    project.json         # binding local_path <-> project_key
