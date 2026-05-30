# Authoring a Ragnarok plugin (frontend SDK v2)

Ragnarok plugins are **frontend-only**. A plugin is installed into the browser
(Plugins tab → *Install plugin…*), runs entirely in the browser, and feeds the
**Ragnarok frontend** — it never talks to the Ragnarok backend. The frontend is
the only thing that calls the Ragnarok backend.

```
plugin  →  Ragnarok frontend (model / constraints JSON)  →  Ragnarok backend  →  frontend  →  plugin (output)
```

A plugin **may have its own backend** (any language, its own HTTP server). Its
JavaScript talks to that backend directly; it must never call the Ragnarok
backend.

## Package layout

A plugin is a `.zip` containing at least:

```
module.json     # manifest (metadata + config schema)
index.js        # JS entry: CommonJS module exporting hook functions
```

`module.json` or the entry may sit at the zip root or one directory deep.

### `module.json`

```jsonc
{
  "id": "my-plugin",                 // required, unique
  "name": "My Plugin",               // required, display name
  "version": "1.0.0",                // optional
  "description": "What it does.",    // optional, shown in the rail/detail
  "entry": "index.js",               // optional, defaults to "index.js"
  "config": {                        // optional default config (free-form JSON)
    "carrier": "solar",
    "minCf": 0.2
  }
}
```

The current config UI is a **JSON editor** (the plugin's `config` object,
editable in the Plugins tab). Whatever the user edits is passed to your hooks as
`config`.

### `index.js` — the hooks

Export any subset of three hooks (CommonJS). Each receives the current `config`.

```js
module.exports = {
  // Replace the whole workbook model (e.g. an importer that builds a network).
  // Return a full model: { sheetName: GridRow[] }.
  transform(model, config) {
    return newModel;
  },

  // Contribute inputs without replacing. Return any of:
  //   sheets:      { sheetName: GridRow[] }  → merged into the model
  //   constraints: string[]                  → DSL lines inserted into the
  //                                            Advanced Constraints code box
  contribute(model, config) {
    return {
      sheets: { generators: [...] },
      constraints: [`cf(${config.carrier}) >= ${config.minCf}`],
    };
  },

  // Post-run: receive the run result JSON and return display analytics
  // (shown as JSON in the plugin's detail pane).
  analyze(result, config) {
    return { total: result.summary?.[0]?.value };
  },
};
```

The Plugins tab shows **Apply to model** when `transform` or `contribute` is
present (transform replaces; contribute merges sheets + inserts constraint
lines), and **Analyze output** when `analyze` is present.

## The model shape

`model` is `Record<sheetName, GridRow[]>` — the workbook as sheets of plain rows
(`Record<string, string | number | boolean | null>`). Sheet/column names follow
the PyPSA schema (`buses`, `generators`, `loads`, `lines`, `links`, `carriers`,
`global_constraints`, the `snapshots` sheet, and `*-<attr>` time-series sheets).
Constraints are best expressed either as `global_constraints` rows (native) or
as DSL lines via `contribute().constraints`.

## Constraint DSL (for `contribute().constraints`)

One linear constraint per line; `#` starts a comment:

```
gen(coal) <= 200000          # carrier energy cap (MWh)
emissions <= 0.5 * gen       # CO2 intensity (tCO2/MWh)
cf(nuclear) >= 0.8           # capacity-factor floor (fraction 0–1)
load_shed <= 0
```

Atoms: `gen[(carrier)]`, `cap[(carrier)]`, `emissions[(carrier)]`, `cf(carrier)`,
`load_shed`, numeric constants; combine with `+ - *` and one of `<= >= ==`. The
frontend compiles these to a structured `constraintSpecs` JSON that the backend
applies — your plugin never sends anything to the backend itself.

## Talking to your own backend

If your plugin needs heavy computation (e.g. building a network), run it in your
own server and `fetch()` it from `index.js`:

```js
async transform(model, config) {
  const resp = await fetch(`${config.backendUrl}/build`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  return await resp.json();   // a Ragnarok model
}
```

Keep that server on its own origin/port. Never point it at, or route through,
the Ragnarok backend.

## Rules

- Frontend-only: never call the Ragnarok backend from a plugin.
- Pure-ish hooks: given the same `config`/`model`, return the same result.
- Fail loudly: throw on bad input; the host surfaces the message as a toast and
  never crashes the app.
