# Repository Guidelines

## Project Structure & Module Organization

This repository contains the SuperTale Community Edition backend and video pipeline. Python source lives under `src/novelvideo/`, with major areas such as `api/` for FastAPI routes, `task_backend/` for job execution, `generators/` for media generation, `verification/` for quality gates, `ports/` for interface boundaries, and `assets/` for bundled media. Operational scripts are in `scripts/`, documentation in `docs/`, examples in `examples/`, and compliance artifacts in `docs/compliance/`, `LICENSES/`, and `sbom.spdx.json`.

## Build and Development Commands

- `uv sync --group dev`: install runtime and development dependencies from `uv.lock`.
- `uv run novelvideo api --port 8780`: start the local REST API.
- Verify changes by direct manual execution of the affected code paths, not by writing test suites.
- `pre-commit run --all-files`: run repository hooks, currently including `gitleaks` secret scanning.

## Coding Style & Naming Conventions

Use Python 3.11-compatible code and keep imports/package paths rooted in `src/novelvideo`. Follow the existing style: 4-space indentation, type hints for public interfaces and dataclass/Pydantic models, snake_case for functions and modules, PascalCase for classes, and uppercase names for constants. Keep route handlers thin and move reusable behavior into services, ports, or task runners matching nearby modules. Avoid committing generated media or local runtime state.

For any frontend visual change, read `DESIGN.md` first — it is the source of truth for colors, typography, spacing, radii, elevation, and motion, and mirrors the CSS variables in `frontend/src/index.css`. When those variables change, update `DESIGN.md` in the same commit and keep `npx @google/design.md lint DESIGN.md` at 0 errors.

## Verification Guidelines

No test suite is kept in this repository (owner directive 2026-09-26). Verify behavior by running the real code paths directly and inspecting their output; do not reintroduce pytest/vitest suites or test scaffolding.

## Commit & Pull Request Guidelines

Recent history uses short conventional prefixes such as `fix:`, `feat(scope):`, `refactor(scope):`, and `chore(scope):`; keep subjects imperative and specific. PRs should describe the user-visible change, list verification commands, link related issues, and include screenshots or sample API output for UI/API contract changes. Note any migration, configuration, model-provider, or compliance impact explicitly.

## Security & Configuration Tips

Do not commit provider keys, signed URLs, credentials, or generated secrets. Configure model access through environment variables such as `MODEL_PROVIDER` and `MODEL_API_KEY`. Run the gitleaks pre-commit hook before sharing changes that touch configuration, provisioning, backup, or gateway code.
