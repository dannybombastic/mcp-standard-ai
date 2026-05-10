# PyPI Release Guide

Este documento explica cómo publicar **ai-context-manager-mcp** a PyPI.

## 🔄 Flujo de Publicación

```
1. Actualizar versión en pyproject.toml
   ↓
2. Commitear cambios
   ↓
3. Crear tag git (v0.2.0)
   ↓
4. GitHub Actions detecta tag
   ↓
5. Build de distribuciones (wheel + sdist)
   ↓
6. Publicar a PyPI
   ↓
7. Disponible para `pip install`
```

## 📋 Requisitos Previos

### 1. Cuenta en PyPI
- Crear una cuenta en https://pypi.org (es gratis)
- Verificar email

### 2. Configurar Trusted Publishers (Recomendado)

**¿Por qué?** Es más seguro que API tokens y no requiere secretos en GitHub.

**Pasos:**
1. Ir a https://pypi.org/manage/account/publishing/
2. Click "Add a new pending publisher"
3. Llenar:
   - **GitHub repository owner**: `dannybombastic`
   - **GitHub repository name**: `mcp-standard-ai`
   - **Workflow name**: `publish-to-pypi.yml`
   - **Workflow ref (branch)**: `main`
4. Click "Add"
5. ✅ Listo! El workflow ahora puede publicar automáticamente

### 3. Alternativa: API Token (Menos seguro)

Si prefieres usar tokens:

1. Crear token en https://pypi.org/manage/account/tokens/
   - Scope: Entire account (o solo este proyecto)
   - Copiar el token
2. En GitHub:
   - Ir a Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Value: Pegar el token
   - Click "Add secret"

**Nota:** El workflow está configurado para OIDC (más seguro). Si usas token, necesitas ajustar el último step.

## 🚀 Cómo Publicar

### Opción 1: Usar el script helper (Recomendado)

```bash
# Ver qué haría sin cambios
python scripts/release.py --version 0.2.0 --dry-run

# Publicar (actualiza versión, commitea, taguea, pushea)
python scripts/release.py --version 0.2.0

# Con mensaje personalizado
python scripts/release.py --version 0.2.0 --message "Add sync workflow improvements"
```

El script automáticamente:
- ✅ Actualiza `pyproject.toml`
- ✅ Commitea con mensaje `chore: bump version to X.Y.Z`
- ✅ Crea tag anotado
- ✅ Pushea a origin
- ✅ Inicia el workflow de PyPI

### Opción 2: Manual

```bash
# 1. Actualizar versión
vim pyproject.toml
# Cambiar: version = "0.1.0" → version = "0.2.0"

# 2. Commitear
git add pyproject.toml
git commit -m "chore: bump version to 0.2.0"

# 3. Crear tag
git tag -a v0.2.0 -m "Release version 0.2.0"

# 4. Pushear
git push origin main
git push origin v0.2.0
```

## 📦 Monitorear la Publicación

1. Ir a GitHub → Actions
2. Ver el workflow "Publish to PyPI" ejecutando
3. Esperar a que termine (2-5 minutos)

**Estados esperados:**
- 🟡 **In progress** → Está construyendo y publicando
- ✅ **Success** → Publicado correctamente!
- ❌ **Failed** → Revisar logs para ver el error

## ✅ Verificar Publicación

Una vez que el workflow termine exitosamente:

### Opción 1: Instalarlo localmente
```bash
pip install --upgrade ai-context-manager-mcp==0.2.0
ai-context-manager --version
```

### Opción 2: Verificar en PyPI
```bash
# Visitar:
https://pypi.org/project/ai-context-manager-mcp/

# O buscar:
pip search ai-context-manager-mcp
```

### Opción 3: Ver en GitHub
```bash
# Releases page:
https://github.com/dannybombastic/mcp-standard-ai/releases
```

## 📝 Versionado

Usar **Semantic Versioning**: MAJOR.MINOR.PATCH

### Ejemplos:
- `v0.1.0` → Inicial
- `v0.1.1` → Bug fix (patch)
- `v0.2.0` → Nuevo feature (minor)
- `v1.0.0` → Breaking changes (major)

### Cuándo incrementar cada número:

| Cambio | Versión | Ejemplo |
|--------|---------|---------|
| Bug fixes | PATCH | 0.1.0 → 0.1.1 |
| Nuevas features (compatible) | MINOR | 0.1.0 → 0.2.0 |
| Breaking changes | MAJOR | 0.2.0 → 1.0.0 |

## 🐛 Troubleshooting

### "Workflow no ejecuta"
- ✅ Tag debe tener formato `v*.*.*` exactamente
- ✅ Tag debe existir en `main` branch
- ✅ Esperar 30 segundos, GitHub a veces tarda

```bash
# Verificar tags:
git tag -l
git describe --tags
```

### "Package already exists on PyPI"
- Usar una versión diferente (incrementar PATCH, MINOR o MAJOR)
- No puedes re-publicar la misma versión

```bash
# Ver versiones publicadas:
pip index versions ai-context-manager-mcp
```

### "Build failed"
- Revisar logs del workflow en GitHub Actions
- Common issues:
  - Syntax errors en Python
  - Dependencias faltantes en `pyproject.toml`
  - README.md no existe o tiene encoding incorrecto

### "Publish failed - Authentication error"
- Si usas OIDC: Verificar que trusted publisher esté configurado en PyPI
- Si usas token: Verificar que `PYPI_API_TOKEN` existe en GitHub Secrets

## 📚 Archivos Importantes

```
.github/workflows/
├── publish-to-pypi.yml     ← Corre en tags, publica a PyPI
└── validate-build.yml      ← Corre en cada push, valida build

scripts/
└── release.py              ← Helper para releases automáticas

pyproject.toml              ← Configuración del proyecto (versión aquí!)

README.md                   ← Mostrado en PyPI
LICENSE                     ← MIT license (requerido)

PYPI_PUBLISHING.md          ← Esta guía
```

## 🔗 Links Útiles

- **PyPI**: https://pypi.org/project/ai-context-manager-mcp/
- **GitHub**: https://github.com/dannybombastic/mcp-standard-ai
- **Semantic Versioning**: https://semver.org/
- **Python Packaging**: https://packaging.python.org/
- **Hatch Docs**: https://hatch.pypa.io/latest/

## ❓ Preguntas Frecuentes

**P: ¿Cuánto tarda en aparecer en pip después de publicar?**  
R: Normalmente 5-10 minutos. PyPI indexa y propaga a CDNs.

**P: ¿Puedo hacer un "prerelease" (0.1.0b1)?**  
R: Sí, usa sufijos como `-alpha`, `-beta`, `-rc1`. PyPI los ordena correctamente.

**P: ¿Qué pasa si publico por error la versión incorrecta?**  
R: No puedes re-publicar la misma versión. Incrementa PATCH y republica:
```bash
# v0.1.0 fue error, corregir con:
git tag -a v0.1.1 -m "Fix: correccion urgente"
git push origin v0.1.1
```

**P: ¿Necesito ejecutar tests antes de publicar?**  
R: Es buena práctica. El workflow `validate-build.yml` ya lo hace en push.

---

**Última actualización:** 2026-05-10  
**Mantenedor:** @dannybombastic
