---
type: skill
name: Python Best Practices
tags: ["python", "best-practices", "code-quality"]
---

# Python Best Practices

## Estilo y formato

- Sigue **PEP 8** para estilo de código. Usa `ruff` o `flake8` para linting.
- Usa `black` para formateo automático consistente.
- Longitud máxima de línea: **88 caracteres** (black default).
- Usa comillas dobles para strings salvo en casos donde se evite escaping.

## Type hints

- Añade type hints en todas las funciones públicas.
- Usa `from __future__ import annotations` para diferir evaluación de tipos.
- Prefiere `X | Y` sobre `Optional[X]` (Python 3.10+).
- Usa `TypeAlias` para tipos complejos reutilizables.

```python
from __future__ import annotations
from pathlib import Path

def load_config(path: Path) -> dict[str, str]:
    ...
```

## Gestión de errores

- Captura excepciones específicas, nunca `except Exception` sin re-raise.
- Usa `contextlib.suppress` para ignorar excepciones esperadas.
- Loguea errores con contexto suficiente para depuración.

## Imports

- Orden: stdlib → third-party → local. Separados por línea en blanco.
- Usa imports absolutos salvo dentro del mismo paquete.
- Evita `from module import *`.

## Funciones y clases

- Una función = una responsabilidad.
- Máximo ~20 líneas por función; si es mayor, refactoriza.
- Prefiere dataclasses o Pydantic sobre dicts para estructuras de datos.
- Usa `__slots__` en clases de datos de alto rendimiento.

## Tests

- Usa `pytest`. Cada función pública tiene al menos un test.
- Sigue el patrón **Arrange / Act / Assert**.
- Usa fixtures para setup compartido; evita mocks excesivos.
