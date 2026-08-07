---
name: framework
description: Use when the user types /framework or asks to adapt a Python project structure to a specific framework (fastapi, django, flask, celery, click). Runs after /architecture — adjusts and extends the existing folder structure to follow framework conventions.
metadata:
  disable-model-invocation: true
  argument-hint: "<framework>"
---

# Framework

Adapt the existing project structure to the conventions of a specific Python framework.

This skill runs **after** `/architecture`. It reads what is already in `src/<package>/`, then adds
or adjusts only what the framework requires — it does not delete or overwrite existing architecture
layers.

Supported frameworks:

| Framework | Use case |
|---|---|
| `fastapi` | Async API REST / OpenAPI |
| `django` | Full-stack web, admin, ORM |
| `flask` | Lightweight web / API |
| `celery` | Distributed task queue / worker |
| `click` | CLI application |

---

## Step 1 — Determine framework and project root

**Framework:** read the argument after `/framework`. If none was provided, ask:

```
ask_followup_question: "Which framework do you want to use?"
suggestion_a: "fastapi — async REST API"
suggestion_b: "django — full-stack web with ORM and admin"
suggestion_c: "flask — lightweight web / API"
suggestion_d: "celery — distributed task queue / background workers"
```

**Project root:** same detection logic as `/architecture` — look for `src/<package>/`. If not found,
ask the user.

**Existing architecture:** list the top-level folders currently under `<root>/` to understand which
pattern(s) were applied. Mention them in the report at the end.

---

## Step 2 — Apply framework-specific additions

### `fastapi`

Add or extend:

```
<root>/
├── api/
│   ├── __init__.py
│   ├── routers/
│   │   └── __init__.py     ← one router file per resource/domain
│   ├── schemas/
│   │   └── __init__.py     ← Pydantic request/response models
│   ├── dependencies/
│   │   └── __init__.py     ← FastAPI Depends() factories
│   └── middleware/
│       └── __init__.py     ← custom Starlette middleware
└── main.py                 ← FastAPI app factory (see stub below)
```

`main.py` stub:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI()

# Register routers here:
# from api.routers import some_router
# app.include_router(some_router.router, prefix="/some", tags=["some"])
```

Add to `pyproject.toml` dependencies if not present: `"fastapi>=0.111.0"`, `"uvicorn[standard]>=0.29.0"`.

---

### `django`

Django has strong conventions — adapt the architecture layers into Django's app model:

```
<root>/                         ← becomes a Django project package
├── settings/
│   ├── __init__.py
│   ├── base.py                 ← shared settings
│   ├── development.py          ← overrides for dev
│   └── production.py           ← overrides for prod
├── urls.py                     ← root URL configuration
├── wsgi.py
├── asgi.py
└── apps/                       ← one Django app per bounded context / resource
    └── <first_app>/
        ├── __init__.py
        ├── models.py           ← Django ORM models (maps to domain/entities if ddd was applied)
        ├── views.py            ← maps to interfaces/api if hexagonal/ddd was applied
        ├── serializers.py      ← DRF serializers (maps to api/schemas)
        ├── urls.py
        ├── admin.py
        └── migrations/
            └── __init__.py
```

Note: if `/architecture ddd` or `/architecture hexagonal` was applied, explain to the user how the
Django app maps to the architecture layers:
- `apps/<name>/models.py` → `domain/entities/`
- `apps/<name>/views.py` → `interfaces/api/`
- `apps/<name>/serializers.py` → `api/schemas/`
- `apps/<name>/migrations/` → `infrastructure/persistence/`

`manage.py` stub at project root (one level above `src/`):

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "<package>.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

Add to `pyproject.toml` dependencies if not present: `"django>=5.0"`.
If using Django REST Framework add: `"djangorestframework>=3.15"`.

---

### `flask`

```
<root>/
├── api/
│   ├── __init__.py
│   ├── blueprints/
│   │   └── __init__.py     ← one Blueprint per resource/domain
│   └── schemas/
│       └── __init__.py     ← marshmallow or pydantic schemas
└── main.py                 ← Flask app factory
```

`main.py` stub:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Flask application entry point."""

from flask import Flask


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)

    # Register blueprints here:
    # from api.blueprints import some_blueprint
    # app.register_blueprint(some_blueprint.bp, url_prefix="/some")

    return app


app = create_app()
```

Add to `pyproject.toml` dependencies if not present: `"flask>=3.0"`.

---

### `celery`

```
<root>/
├── tasks/
│   └── __init__.py         ← Celery task definitions
├── workers/
│   └── __init__.py         ← worker configuration and entrypoints
├── schedules/
│   └── __init__.py         ← beat schedules (periodic tasks)
└── celery_app.py           ← Celery app factory (see stub below)
```

`celery_app.py` stub:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Celery application factory."""

from celery import Celery

celery_app = Celery(__name__)

# Configuration loaded from core.config:
# celery_app.conf.broker_url = settings.celery.broker_url
# celery_app.conf.result_backend = settings.celery.result_backend

# Auto-discover tasks:
# celery_app.autodiscover_tasks(["tasks"])
```

Add to `pyproject.toml` dependencies if not present: `"celery>=5.4"`.

---

### `click`

```
<root>/
├── commands/
│   └── __init__.py         ← one file per command group
└── main.py                 ← Click CLI entry point
```

`main.py` stub:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""CLI entry point."""

import click


@click.group()
def cli() -> None:
    """<package> command-line interface."""


# Register command groups here:
# from commands import some_group
# cli.add_command(some_group.group)

if __name__ == "__main__":
    cli()
```

Add to `pyproject.toml` under `[project.scripts]` if not present:
```toml
[project.scripts]
<package> = "<package>.main:cli"
```

Add to `pyproject.toml` dependencies if not present: `"click>=8.1"`.

---

## Step 3 — Write the files

Use `write_file` to create every new file from Step 2. Use `apply_diff` to extend existing files
(e.g. adding a new section to `pyproject.toml`).

Each new `__init__.py` must follow the standard header + docstring + `__all__` pattern (same as
`/architecture` Step 3).

Do **not** overwrite `__init__.py` files that already exist with content — use `apply_diff` to
extend them.

---

## Step 4 — Report to the user

Show:
1. Which framework was applied.
2. Which architecture layers were already present (detected in Step 1).
3. The files created or modified (with clickable paths).
4. How the framework maps onto the architecture layers (if ddd/hexagonal was used).

Then remind the user of the next step:

```
Next step:
/add-python-config    — generate the configuration module in core/config.py
```
