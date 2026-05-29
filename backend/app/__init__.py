"""Ragnarok backend host (engine-agnostic).

This package is the FastAPI application and everything that does *not* depend on
a specific optimisation engine:

- ``main``: the FastAPI app, run lifecycle (job store, subprocess worker), and
  the PyPSA-format file converter endpoints.
- ``models``: request/response pydantic models (``RunPayload``).
- ``config``: loads ``backend/config/*.json`` (system defaults).
- ``backends``: the pluggable-backend seam (``Backend`` protocol + registry).

Plugins are intentionally a frontend-only concern: the backend never discovers,
loads, or executes plugin code. It only ever receives ``{model, scenario,
options}`` and solves.

The engine that actually builds and solves a network lives in a sibling package
(``backend.pypsa`` today). The host selects it via ``options["backend"]`` and
never imports engine internals directly except through the registry and the
file-converter endpoints.
"""
