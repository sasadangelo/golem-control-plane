---
name: python-cli
description: >
  Use when the user wants to design and implement a Python CLI application.
  Activated by /python-cli. Guides through three phases: domain modeling (entities and
  relationships), CLI command/subcommand design, and implementation using Typer + the Command Pattern.
metadata:
  argument-hint: "[project description or domain]"
---

# Python CLI — Design & Implementation Guide

Follow these phases **in order**. Never jump to implementation before the domain model and
CLI design are approved by the user.

---

## Phase 0 — Context Detection

Before anything else, determine the starting context. Use `ask_followup_question` to ask:

> "Are you adding a CLI to an existing project, or starting a new project from scratch?"

Then branch:

### Case A — Existing project

1. Use `list_files` (recursive) and `read_file` on `pyproject.toml` to understand the current
   structure: what packages exist, what dependencies are already declared, whether a `cli.py` or
   entry point is already present.
2. Use `grep` to find domain entities already modelled in code (models, dataclasses, Pydantic
   schemas, ORM classes). These are the resources for Phase 1 — do **not** ask the user to
   re-describe what the code already shows.
3. Check whether `typer` is already a dependency. If not, note it must be added in Phase 3.
4. Identify where `commands/` should live relative to the existing package structure.
5. Proceed to Phase 1 in **discovery mode**: present the entities found to the user for
   confirmation rather than asking from scratch.

### Case B — New project

No discovery needed. Proceed directly to Phase 1 in **brainstorming mode**: ask the user to
describe the domain from scratch.
`uv init` and full scaffolding will be done in Phase 3.

---

## Phase 1 — Domain Modeling

Before writing any code, model the domain. The domain defines the **resources** the CLI will
manipulate — exactly like the resources of a REST API.

Use `ask_followup_question` to collect:

1. **What is the domain?** Ask the user to describe in plain language what the CLI manages
   (e.g. "task manager", "cloud resource provisioner", "data pipeline runner").
2. **What are the resources (entities)?** Identify the nouns — these become the top-level commands.
   Examples: `project`, `task`, `user`, `job`, `cluster`.
3. **What are the relationships between resources?** Map cardinality (1:1, 1:N, M:N).
   Relationships determine **navigation depth** in the CLI:
   - A **strong relationship** (child only exists in the context of a parent) → child becomes a
     nested subcommand under the parent: `cli project task list --project-id 1`
   - A **weak relationship** (child can exist independently, parent is just a filter) → child stays
     at the top level with the parent ID as an option: `cli task list --project-id 1`
   - Maximum navigation depth is **2 levels** (root → resource → sub-resource). Beyond that, use
     contextual options instead of deeper nesting.

Produce a **domain table** before moving on:

| Resource | Relationship | Notes |
|---|---|---|
| `project` | root resource | Independent, top-level |
| `task` | project (1:N, strong) | Task only exists inside a project |
| `stats` | aggregates task data | Logical grouping, not a stored resource |

Do not proceed to Phase 2 until the user confirms the domain table.

---

## Phase 2 — CLI Design

Translate the domain model into a concrete CLI syntax. The design follows the same logic as a
REST API: **resources are commands, HTTP verbs map to subcommands**.

### Verb mapping (REST → CLI)

| HTTP method | CLI subcommand | Meaning |
|---|---|---|
| `GET /resources` | `list` | List all instances |
| `GET /resources/{id}` | `show` | Show one instance |
| `POST /resources` | `add` / `create` | Create a new instance |
| `PUT /resources/{id}` | `update` | Update an existing instance |
| `DELETE /resources/{id}` | `delete` / `remove` | Delete an instance |

Add domain-specific verbs where needed: `run`, `export`, `import`, `sync`, `publish`.

### Naming conventions

- Commands = resource names (singular noun): `project`, `task`, `user`
- Subcommands = action verbs: `list`, `add`, `show`, `update`, `delete`
- Options use `--kebab-case`; short aliases use a single letter `-x`
- Path parameters (e.g. `{id}`) become required options: `--id/-i`
- Body fields become required or optional options: `--name/-n`, `--output/-o`
- Positional arguments only for truly unambiguous single values; prefer named options otherwise

### Nested resources (strong relationships, max 2 levels)

When a resource only exists in the context of a parent, nest it:

```
cli project list
cli project add   --name "..."
cli project show  --id 1
cli project task list   --project-id 1
cli project task add    --project-id 1 --name "..."
cli project task delete --project-id 1 --id 3
```

When a resource is independent (weak relationship), keep it at the top level:

```
cli task list --project-id 1     # project-id is a filter, not a context
```

### Design table

For each resource and operation, produce a command table:

| Command | Subcommand | Options / Args | Description |
|---|---|---|---|
| `project` | `list` | — | List all projects |
| `project` | `add` | `--name/-n` (str, required) | Create a project |
| `project` | `show` | `--id/-i` (int, required) | Show project details |
| `project` | `delete` | `--id/-i` (int, required) | Delete a project |
| `project task` | `list` | `--project-id/-p` (int, required) | List tasks in a project |
| `project task` | `add` | `--project-id/-p` (int, required), `--name/-n` (str, required) | Add a task |
| `project task` | `delete` | `--project-id/-p` (int, required), `--id/-i` (int, required) | Delete a task |
| `stats` | `summary` | — | Print statistics |
| `stats` | `export` | `--output/-o` (str, default: report.csv) | Export to CSV |

### Usage examples

Write the full CLI invocation for every command before moving on:

```
cli project list
cli project add --name "Website redesign"
cli project show --id 1
cli project delete --id 1
cli project task list --project-id 1
cli project task add --project-id 1 --name "Buy milk"
cli project task delete --project-id 1 --id 3
cli stats summary
cli stats export --output report.csv
```

Do not proceed to Phase 3 until the user confirms the command table and examples.

---

## Phase 3 — Implementation

### Technology stack

- **Typer** for CLI parsing and dispatch. Typer sits on top of Click and infers argument types,
  required flags, and help text directly from Python type annotations — no separate `@click.option`
  decorators needed. This keeps signatures as the single source of truth and integrates cleanly
  with mypy.
- **Command Pattern** for business logic. Typer handles dispatch; command classes encapsulate
  behavior. One class per resource (or logical group), not one class per subcommand.
- Follow the **python-style-guide** skill conventions: modern type hints (`X | None`, `list[str]`),
  Google docstrings, ruff formatting, `uv` for dependency management.

### Project structure

```
<project-name>/
├── pyproject.toml
├── README.md
└── src/
    └── <project_name>/
        ├── __init__.py
        ├── cli.py                      ← Typer app wiring only, no business logic
        └── commands/
            ├── __init__.py
            ├── base.py                 ← Marker ABC
            ├── <resource>_command.py   ← One file per resource or logical group
            └── ...
```

### Base command class

The base class is a **marker** only. Typer handles dispatch, so no shared `execute(args)` method
is needed or wanted — it would break type safety:

```python
# commands/base.py
from abc import ABC


class Command(ABC):
    """Marker base class for CLI commands.

    Typer handles argument parsing and command dispatch.
    Each subclass defines its own typed method signatures.
    """
```

### Typer app wiring (cli.py)

`cli.py` contains only wiring — Typer app declarations, `add_typer` calls, and thin wrapper
functions that delegate immediately to command classes:

```python
# cli.py
import typer

from <project_name>.commands.project_command import ProjectCommand
from <project_name>.commands.stats_command import StatsCommand

app = typer.Typer(help="<Project> CLI")

# Sub-apps for resources with subcommands
project_app = typer.Typer(help="Manage projects")
project_task_app = typer.Typer(help="Manage tasks within a project")
stats_app = typer.Typer(help="Statistics")

app.add_typer(project_app, name="project")
project_app.add_typer(project_task_app, name="task")
app.add_typer(stats_app, name="stats")

_project = ProjectCommand()
_stats = StatsCommand()


@project_app.command("list")
def project_list() -> None:
    """List all projects."""
    _project.list()


@project_app.command("add")
def project_add(
    name: str = typer.Option(..., "--name", "-n", help="Project name"),
) -> None:
    """Create a new project."""
    _project.add(name=name)


@project_task_app.command("list")
def task_list(
    project_id: int = typer.Option(..., "--project-id", "-p", help="Project ID"),
) -> None:
    """List all tasks in a project."""
    _project.task_list(project_id=project_id)


@project_task_app.command("add")
def task_add(
    project_id: int = typer.Option(..., "--project-id", "-p", help="Project ID"),
    name: str = typer.Option(..., "--name", "-n", help="Task name"),
) -> None:
    """Add a task to a project."""
    _project.task_add(project_id=project_id, name=name)


@stats_app.command("summary")
def stats_summary() -> None:
    """Show statistics summary."""
    _stats.summary()


@stats_app.command("export")
def stats_export(
    output: str = typer.Option("report.csv", "--output", "-o", help="Output file"),
) -> None:
    """Export statistics to CSV."""
    _stats.export(output=output)


def main() -> None:
    app()
```

### Command class (one per resource, typed methods)

```python
# commands/project_command.py
from .base import Command


class ProjectCommand(Command):
    """Encapsulates all project and project-task operations."""

    def list(self) -> None:
        """List all projects."""
        ...

    def add(self, name: str) -> None:
        """Create a new project."""
        ...

    def task_list(self, project_id: int) -> None:
        """List tasks belonging to a project."""
        ...

    def task_add(self, project_id: int, name: str) -> None:
        """Add a task to a project."""
        ...
```

Nested sub-resource operations live on the **parent resource command class** when the relationship
is strong (child only exists in parent context). If the sub-resource grows large enough to warrant
its own class, extract it and inject it into the parent command.

### pyproject.toml entry point

```toml
[project.scripts]
cli = "<project_name>.cli:main"
```

Install with `uv pip install -e .` — the CLI is then available as `cli <command> ...`.

### Implementation checklist

**Case B — New project:**

- [ ] Scaffold project with `uv init`
- [ ] Add dependency: `uv add typer`
- [ ] Create package structure: `src/<project_name>/commands/`
- [ ] Write `commands/base.py` (marker ABC)
- [ ] Write one command class per resource from the Phase 2 table
- [ ] Wire all commands in `cli.py` (wiring only, no logic)
- [ ] Add entry point in `pyproject.toml`
- [ ] `uv pip install -e .` and smoke-test every example from Phase 2
- [ ] `ruff check . && ruff format .`
- [ ] `mypy src/` — fix all errors before declaring done

**Case A — Existing project:**

- [ ] If `typer` not in dependencies: `uv add typer`
- [ ] Create `commands/` under the existing package (location identified in Phase 0)
- [ ] Write `commands/base.py` (marker ABC)
- [ ] Write one command class per resource from the Phase 2 table, reusing existing
      models/services — do not duplicate domain logic already in the codebase
- [ ] Wire all commands in `cli.py` (create it if absent, otherwise extend it)
- [ ] Add or update entry point in `pyproject.toml` if not already present
- [ ] `uv pip install -e .` and smoke-test every example from Phase 2
- [ ] `ruff check . && ruff format .`
- [ ] `mypy src/` — fix all errors before declaring done

---

## Key design rules (always apply)

1. **Domain first.** Entities are resources. Relationships determine navigation depth.
2. **Resources → commands. Verbs → subcommands.** The same logic as REST.
3. **Max 2 levels of nesting.** Deeper hierarchies become options, not more subcommands.
4. **Typer dispatches, command classes encapsulate.** `cli.py` is wiring only.
5. **One command class per resource** (or logical group) — not one class per subcommand.
6. **No shared `execute(args)` method.** Each method has its own explicit typed signature.
7. **Typed signatures are the spec.** If mypy complains, the design has a gap.
8. **Help text on every command and option.** `--help` output is the user-facing contract.
