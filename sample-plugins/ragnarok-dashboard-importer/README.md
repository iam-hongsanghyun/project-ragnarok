# Dashboard Importer

`ragnarok-dashboard-importer` is a `pre-build` plugin that brings
[`simplePyPSA_KR`](https://github.com/iam-hongsanghyun/simplePyPSA_KR)-style
`dashboard.xlsx` workflows into Ragnarok without requiring the source repo to be
installed on the target machine.

The plugin vendors the dashboard build logic it needs, builds the pre-solve
PyPSA network directly from the dashboard workbook and the model workbook it
references, then converts that network into Ragnarok's native workbook JSON
before `build_network()` runs.

## What it is for

- reuse the existing dashboard rules from `simplePyPSA_KR`
- build the same pre-optimisation network that `gui_app.py` would build
- hand that network to Ragnarok as an in-memory workbook model
- optionally keep Ragnarok-authored `loads` and `loads-p_set` sheets

## Config

- `dashboard_path`
  - path to `dashboard.xlsx`
- `preserve_existing_loads`
  - when `true`, non-empty incoming `loads` and `loads-p_set` sheets from Ragnarok override the imported dashboard export
  - use this only when those loads already point at buses that will exist after the dashboard import
- `export_path`
  - optional debug path for exporting the built Ragnarok workbook model as XLSX

Both path fields support `${HOME}` and `${PROJECT_ROOT}` placeholders.

## Runtime requirements

- the plugin needs access to the dashboard workbook
- the dashboard workbook must point at a model workbook that also exists on disk
- if the model path inside the dashboard is relative, it is resolved relative to the dashboard file

## Typical use

1. Install the plugin zip in Ragnarok.
2. Set `dashboard_path` to the dashboard workbook you already use in `simplePyPSA_KR`.
3. Enable `preserve_existing_loads` only when your Ragnarok-side loads already use bus names compatible with the imported dashboard model.
4. Run Ragnarok.

The plugin returns a full Ragnarok workbook model at `pre-build`, so the rest of
the solve pipeline is unchanged.
