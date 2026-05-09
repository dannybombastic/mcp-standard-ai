---
type: skill
name: Git Workflow
tags: ["git", "workflow", "branching", "commits"]
---

# Git Workflow

## Estrategia de ramas

Sigue **GitHub Flow** (o Trunk-Based Development para equipos avanzados):

- `main` — rama principal, siempre desplegable.
- `feature/<ticket>-descripcion` — nuevas funcionalidades.
- `fix/<ticket>-descripcion` — correcciones de bugs.
- `chore/<descripcion>` — tareas de mantenimiento sin lógica de negocio.

## Commits

Usa el estándar **Conventional Commits**:

```
<type>(<scope>): <descripción corta en imperativo>

[cuerpo opcional]

[footer opcional: BREAKING CHANGE, Closes #123]
```

Tipos permitidos: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`.

**Ejemplos:**
```
feat(auth): add JWT refresh token endpoint
fix(api): handle null response from upstream service
docs(readme): update installation instructions
```

## Pull Requests

- Un PR = un cambio coherente. Evita PRs con múltiples concerns.
- Título del PR en formato Conventional Commits.
- Descripción incluye: **qué**, **por qué**, **cómo probar**.
- Requiere al menos 1 reviewer aprobación antes de merge.
- Usa **Squash and Merge** para mantener historial limpio.

## Reglas generales

- Nunca hacer force-push en `main`.
- Sincroniza tu rama con `main` mediante `git rebase`, no `merge`.
- Borra la rama remota tras el merge.
- Usa `.gitignore` apropiado desde el inicio del proyecto.
