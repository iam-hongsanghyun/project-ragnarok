from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_module_host_config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _cfg() -> dict[str, Any]:
    return load_module_host_config()


def _sdk_version() -> str:
    return str(_cfg().get("sdk_version", "1"))


def _supported_capabilities() -> list[str]:
    return [str(item) for item in _cfg().get("capabilities", [])]


def _supported_permissions() -> list[str]:
    return [str(item) for item in _cfg().get("permissions", [])]


def _expand_path(raw: str) -> Path:
    text = str(raw)
    text = text.replace("${HOME}", str(Path.home()))
    text = text.replace("${PROJECT_ROOT}", str(PROJECT_ROOT))
    return Path(text).expanduser().resolve()


def _root_descriptors() -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    for item in _cfg().get("search_roots", []):
        raw_path = str(item.get("path", ""))
        resolved = _expand_path(raw_path)
        roots.append({
            "label": str(item.get("label", resolved.name or resolved.as_posix())),
            "path": str(resolved),
            "configuredPath": raw_path,
            "exists": resolved.exists(),
            "isDirectory": resolved.is_dir(),
        })
    return roots


def validate_manifest(manifest: dict[str, Any], module_dir: Path | None = None) -> dict[str, Any]:
    diagnostics: list[str] = []
    supported_capabilities = set(_supported_capabilities())
    supported_permissions = set(_supported_permissions())

    module_id = str(manifest.get("id", "")).strip()
    name = str(manifest.get("name", "")).strip()
    version = str(manifest.get("version", "")).strip()
    sdk_version = str(manifest.get("sdkVersion", "")).strip()
    entry = str(manifest.get("entry", "")).strip()
    description = str(manifest.get("description", "")).strip()
    capabilities = [str(item).strip() for item in manifest.get("capabilities", []) if str(item).strip()]
    permissions = [str(item).strip() for item in manifest.get("permissions", []) if str(item).strip()]

    for field_name, value in (
        ("id", module_id),
        ("name", name),
        ("version", version),
        ("sdkVersion", sdk_version),
        ("entry", entry),
    ):
        if not value:
            diagnostics.append(f"Missing required field '{field_name}'.")

    if not capabilities:
        diagnostics.append("Manifest must declare at least one capability.")

    unsupported_capabilities = sorted(set(capabilities) - supported_capabilities)
    if unsupported_capabilities:
        diagnostics.append(
            "Unsupported capabilities: " + ", ".join(unsupported_capabilities) + "."
        )

    unsupported_permissions = sorted(set(permissions) - supported_permissions)
    if unsupported_permissions:
        diagnostics.append(
            "Unsupported permissions: " + ", ".join(unsupported_permissions) + "."
        )

    compatible = sdk_version == _sdk_version()
    if sdk_version and not compatible:
        diagnostics.append(
            f"Incompatible sdkVersion '{sdk_version}' (host supports '{_sdk_version()}')."
        )

    entry_exists = False
    entry_path = ""
    if entry:
        if Path(entry).is_absolute():
            diagnostics.append("Manifest entry must be a relative path inside the module directory.")
        elif module_dir is not None:
            candidate = (module_dir / entry).resolve()
            entry_path = str(candidate)
            entry_exists = candidate.exists() and candidate.is_file()
            if not entry_exists:
                diagnostics.append(f"Entrypoint file not found: {candidate}")

    valid = len([d for d in diagnostics if not d.startswith("Incompatible sdkVersion")]) == 0
    status = "ready"
    if not valid:
        status = "invalid"
    elif not compatible:
        status = "incompatible"

    return {
        "id": module_id,
        "name": name,
        "version": version,
        "sdkVersion": sdk_version,
        "entry": entry,
        "entryPath": entry_path,
        "entryExists": entry_exists,
        "description": description,
        "capabilities": capabilities,
        "permissions": permissions,
        "compatible": compatible,
        "valid": valid,
        "status": status,
        "diagnostics": diagnostics,
    }


def validate_manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    manifest = payload if isinstance(payload, dict) else {}
    result = validate_manifest(manifest)
    return {
        "hostSdkVersion": _sdk_version(),
        "supportedCapabilities": _supported_capabilities(),
        "supportedPermissions": _supported_permissions(),
        "manifest": result,
    }


def discover_modules() -> dict[str, Any]:
    roots = _root_descriptors()
    modules: list[dict[str, Any]] = []
    ids_to_indexes: dict[str, list[int]] = {}

    for root in roots:
        if not root["exists"] or not root["isDirectory"]:
            continue
        root_path = Path(root["path"])
        candidates: list[Path] = []
        if (root_path / "module.json").exists():
            candidates.append(root_path)
        for child in sorted(root_path.iterdir()):
            if child.is_dir() and (child / "module.json").exists():
                candidates.append(child)
        for module_dir in candidates:
            manifest_path = module_dir / "module.json"
            try:
                manifest = json.loads(manifest_path.read_text())
            except Exception as exc:  # noqa: BLE001
                modules.append({
                    "id": module_dir.name,
                    "name": module_dir.name,
                    "version": "",
                    "sdkVersion": "",
                    "entry": "",
                    "entryPath": "",
                    "entryExists": False,
                    "description": "",
                    "capabilities": [],
                    "permissions": [],
                    "compatible": False,
                    "valid": False,
                    "status": "invalid",
                    "diagnostics": [f"Could not parse module.json: {exc}"],
                    "manifestPath": str(manifest_path),
                    "modulePath": str(module_dir),
                    "rootLabel": root["label"],
                    "rootPath": root["path"],
                })
                continue

            validated = validate_manifest(manifest, module_dir=module_dir)
            descriptor = {
                **validated,
                "manifestPath": str(manifest_path),
                "modulePath": str(module_dir),
                "rootLabel": root["label"],
                "rootPath": root["path"],
            }
            modules.append(descriptor)
            if descriptor["id"]:
                ids_to_indexes.setdefault(descriptor["id"], []).append(len(modules) - 1)

    for module_id, indexes in ids_to_indexes.items():
        if len(indexes) < 2:
            continue
        for idx in indexes:
            modules[idx]["valid"] = False
            modules[idx]["status"] = "invalid"
            modules[idx]["diagnostics"] = list(modules[idx]["diagnostics"]) + [
                f"Duplicate module id '{module_id}' discovered in multiple module roots."
            ]

    summary = {
        "discovered": len(modules),
        "ready": sum(1 for m in modules if m["status"] == "ready"),
        "invalid": sum(1 for m in modules if m["status"] == "invalid"),
        "incompatible": sum(1 for m in modules if m["status"] == "incompatible"),
    }

    return {
        "host": {
            "sdkVersion": _sdk_version(),
            "runtimeMode": str(_cfg().get("runtime_mode", "manifest-discovery")),
            "supportedCapabilities": _supported_capabilities(),
            "supportedPermissions": _supported_permissions(),
        },
        "roots": roots,
        "modules": modules,
        "summary": summary,
    }
