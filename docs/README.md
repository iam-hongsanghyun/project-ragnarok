# Ragnarok Documentation

Ragnarok is a browser-based GUI for building and running PyPSA power-system models.
This directory holds all project documentation. The top-level
[README.md](../README.md) stays at the repository root; everything else lives here.

## Structure

```
docs/
  README.md            this index
  CAPABILITIES.md      what Ragnarok can and cannot do (code-checked)
  SUPPORT_MATRIX.md    generated feature support matrix (npm run generate:support-matrix)
  TODO.md              living project task log and roadmap
  architecture/        how the system is built and how each process works
    ARCHITECTURE.md    system overview, tech stack, repo layout, data flow
    PROCESSES.md       step-by-step logic of each process (open, run, build, solve, export)
    DESIGN.md          UI design philosophy
  guides/              human-facing how-to documentation
    USER_MANUAL.md     end-user manual for analysts
    module-system-v1.md        plugin system specification
    module-authoring-guide.md  how to write a plugin
  reference/           per-module function reference (backend + frontend)
```

## Start here

| If you want to… | Read |
|---|---|
| Understand the whole system fast | [architecture/ARCHITECTURE.md](./architecture/ARCHITECTURE.md) |
| Follow exactly what happens in each process | [architecture/PROCESSES.md](./architecture/PROCESSES.md) |
| Know what the product can and cannot do | [CAPABILITIES.md](./CAPABILITIES.md) |
| Use the app as an analyst | [guides/USER_MANUAL.md](./guides/USER_MANUAL.md) |
| Write a plugin | [guides/module-authoring-guide.md](./guides/module-authoring-guide.md) |
| Look up a specific function or component | [reference/](./reference/) |
| See the roadmap and task history | [TODO.md](./TODO.md) |
