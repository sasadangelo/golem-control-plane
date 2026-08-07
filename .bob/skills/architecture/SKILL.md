---
name: architecture
description: Use when the user types /architecture or asks to define the architecture of a Python project. Generates the folder structure and stub files for the chosen architectural pattern (layered, hexagonal, ddd, event-driven, pipeline) or a combination of patterns separated by spaces.
metadata:
  disable-model-invocation: true
  argument-hint: "<pattern> [pattern ...]"
---

# Architecture

Scaffold the folder structure and stub `__init__.py` files for one or more architectural patterns.

Supported patterns (may be combined):

| Pattern | Alias accepted | Best for |
|---|---|---|
| `layered` | — | API REST, CLI, microservizi semplici |
| `hexagonal` | `hex` | Massima testabilità, swap di infrastruttura |
| `ddd` | — | Dominio complesso, bounded contexts |
| `event-driven` | `events` | Worker, consumer, pipeline reattive |
| `pipeline` | — | ETL, batch, ML preprocessing |

Common combinations:
- `hexagonal ddd` — API con dominio complesso (il combo più usato in produzione)
- `ddd cqrs` — Dominio complesso + read/write separati (nota: `cqrs` è accettato come terzo pattern addizionale)
- `event-driven pipeline` — Worker che consuma eventi e li trasforma in step

---

## Step 1 — Determine patterns and project root

**Patterns:** read the argument(s) after `/architecture`. If none were provided, ask:

```
ask_followup_question: "Which architectural pattern(s) do you want to apply?"
suggestion_a: "layered — API REST or simple microservice (most common)"
suggestion_b: "hexagonal ddd — API with complex domain (recommended for production)"
suggestion_c: "event-driven pipeline — worker / consumer / ETL"
suggestion_d: "ddd cqrs — complex domain with separate read/write models"
```

Normalise aliases: `hex` → `hexagonal`, `events` → `event-driven`.

**Project root:** Look for an existing `src/<package>/` directory in the workspace. If exactly one
package exists under `src/`, use `src/<package>/` as the root. If none exists or there are multiple,
ask:

```
ask_followup_question: "Where is the package root?"
suggestion_a: "src/<package>/ (detected or most common)"
suggestion_b: "Enter a custom path"
```

---

## Step 2 — Build the folder map

Merge the folder maps for all requested patterns. Where two patterns define the same top-level
folder, keep both subtrees merged (do not overwrite).

### `layered`

```
<root>/
├── api/
│   ├── __init__.py
│   ├── routers/
│   │   └── __init__.py
│   └── schemas/
│       └── __init__.py
├── services/
│   └── __init__.py
├── repositories/
│   └── __init__.py
├── models/
│   └── __init__.py
└── core/
    ├── __init__.py
    ├── config.py          ← placeholder, filled by /add-python-config
    └── log.py             ← placeholder
```

### `hexagonal`

```
<root>/
├── domain/
│   ├── __init__.py
│   └── ports/
│       └── __init__.py    ← abstract interfaces (input + output ports)
├── application/
│   └── __init__.py        ← use cases / application services
├── infrastructure/
│   ├── __init__.py
│   ├── adapters/
│   │   └── __init__.py    ← concrete implementations of output ports
│   └── driven/
│       └── __init__.py    ← DB, HTTP clients, message broker adapters
├── interfaces/
│   ├── __init__.py
│   └── api/
│       └── __init__.py    ← driving adapters (HTTP, CLI, consumer)
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

### `ddd`

```
<root>/
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   └── __init__.py    ← domain entities and aggregates
│   ├── value_objects/
│   │   └── __init__.py
│   ├── events/
│   │   └── __init__.py    ← domain events
│   └── repositories/
│       └── __init__.py    ← repository interfaces (abstract)
├── application/
│   ├── __init__.py
│   ├── commands/
│   │   └── __init__.py
│   └── handlers/
│       └── __init__.py
├── infrastructure/
│   ├── __init__.py
│   └── persistence/
│       └── __init__.py    ← concrete repository implementations
├── interfaces/
│   ├── __init__.py
│   └── api/
│       └── __init__.py
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

### `event-driven`

```
<root>/
├── consumers/
│   └── __init__.py        ← event listeners / message handlers
├── producers/
│   └── __init__.py        ← event publishers
├── processors/
│   └── __init__.py        ← business logic per event type
├── models/
│   └── __init__.py        ← event schemas / data models
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

### `pipeline`

```
<root>/
├── steps/
│   └── __init__.py        ← individual pipeline steps / transforms
├── pipelines/
│   └── __init__.py        ← pipeline definitions (ordered step sequences)
├── models/
│   └── __init__.py        ← input/output data models per step
├── io/
│   └── __init__.py        ← sources (readers) and sinks (writers)
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

### `cqrs` (additive — use only in combination with `ddd` or `hexagonal`)

Adds inside `application/`:

```
<root>/application/
├── commands/
│   └── __init__.py        ← command definitions
├── queries/
│   └── __init__.py        ← query definitions
├── command_handlers/
│   └── __init__.py
└── query_handlers/
    └── __init__.py
```

---

## Step 3 — Write the files

For every folder in the merged map, create the corresponding `__init__.py` using `write_file`.

Each `__init__.py` must contain:
1. The standard copyright header (from python-style-guide).
2. A one-line module-level docstring describing the layer's responsibility (use the comment from the
   folder map above as the description).
3. An empty `__all__: list[str] = []` — to be filled as the module grows.

Example for `domain/entities/__init__.py`:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Domain entities and aggregates."""

__all__: list[str] = []
```

For `core/config.py` write a minimal placeholder:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Application configuration — run /add-python-config to populate this module."""
```

For `core/log.py` write a minimal placeholder:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Logging setup — add your setup_logger() factory here."""
```

---

## Step 4 — Report to the user

Show the full folder tree created (use ASCII tree format). Then remind the user of the recommended
next steps:

```
Next steps:
1. /framework <name>        — adapt this structure to your framework (fastapi, django, flask, …)
2. /add-python-config       — generate the configuration module in core/config.py
```

If `core/config.py` was already populated by a previous `/add-python-config` run, skip step 2 from
the reminder.
