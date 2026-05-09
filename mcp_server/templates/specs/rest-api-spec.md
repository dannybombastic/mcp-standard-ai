---
type: spec
name: REST API Specification
tags: ["api", "rest", "openapi", "http"]
---

# REST API Specification

## Convenciones generales

- **Base URL**: `https://api.example.com/v1`
- **Formato**: JSON (`Content-Type: application/json`)
- **Autenticación**: Bearer token en header `Authorization: Bearer <token>`
- **Versioning**: en la URL (`/v1/`, `/v2/`)

## Estructura de respuesta

### Éxito
```json
{
  "data": { ... },
  "meta": {
    "page": 1,
    "total": 100
  }
}
```

### Error
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "El recurso solicitado no existe.",
    "details": []
  }
}
```

## Códigos HTTP

| Código | Uso |
|--------|-----|
| 200 | OK — operación exitosa |
| 201 | Created — recurso creado |
| 204 | No Content — DELETE exitoso |
| 400 | Bad Request — validación fallida |
| 401 | Unauthorized — sin autenticación |
| 403 | Forbidden — sin permisos |
| 404 | Not Found — recurso no existe |
| 409 | Conflict — estado inconsistente |
| 422 | Unprocessable Entity — lógica de negocio fallida |
| 429 | Too Many Requests — rate limit |
| 500 | Internal Server Error |

## Nomenclatura de endpoints

- Sustantivos en plural: `/users`, `/projects`, `/assets`
- Relaciones anidadas: `/projects/{id}/assets`
- Acciones no-CRUD como sub-recursos: `/assets/{id}/publish`
- kebab-case para paths multi-palabra: `/api-keys`, `/cloud-sync`

## Paginación

```
GET /assets?page=1&page_size=20
```

Respuesta incluye `meta.page`, `meta.page_size`, `meta.total`, `meta.total_pages`.

## Filtrado y ordenación

```
GET /assets?type=skill&tags=python&sort=-created_at
```

- Prefijo `-` en sort indica orden descendente.
- Múltiples tags separados por coma: `tags=python,backend`.
