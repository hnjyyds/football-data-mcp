from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "football_data_mcp"


class FakeMCP:
    def __init__(self) -> None:
        self.routes: dict[str, dict[str, Any]] = {}

    def custom_route(self, path: str, *, methods: list[str], include_in_schema: bool) -> Any:
        def decorator(func: Any) -> Any:
            self.routes[path] = {
                "methods": methods,
                "include_in_schema": include_in_schema,
                "handler": func,
            }
            return func

        return decorator


def _python_files(path: Path) -> list[Path]:
    return sorted(p for p in path.rglob("*.py") if p.name != "__init__.py")


def _imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_http_routes_are_registered_by_controller_registry() -> None:
    registry = importlib.import_module("football_data_mcp.api.registry")
    fake_mcp = FakeMCP()

    registered = registry.register_controllers(fake_mcp)

    assert "/api/project" in fake_mcp.routes
    assert any(item["module"].endswith(".project") for item in registered)
    assert all(item["routes"] for item in registered)


def test_server_does_not_declare_http_controller_routes_directly() -> None:
    server_source = (PACKAGE_ROOT / "server.py").read_text(encoding="utf-8")

    assert "@mcp.custom_route" not in server_source


def test_controllers_do_not_import_dal_modules() -> None:
    controller_root = PACKAGE_ROOT / "api" / "controllers"
    forbidden = {
        "football_data_mcp.sources",
        "football_data_mcp.learning_store",
        "football_data_mcp.snapshot_store",
        "football_data_mcp.db_janitor",
        "football_data_mcp.data_sources_registry",
        "football_data_mcp.profitability_calculator",
    }

    for path in _python_files(controller_root):
        imports = _imports_in_file(path)
        violations = sorted(name for name in imports if name in forbidden)
        assert violations == [], f"{path.relative_to(PROJECT_ROOT)} imports DAL modules: {violations}"


def test_services_do_not_import_http_controller_schemas() -> None:
    service_root = PACKAGE_ROOT / "services"
    forbidden_prefix = "football_data_mcp.api.schemas"

    for path in _python_files(service_root):
        imports = _imports_in_file(path)
        violations = sorted(name for name in imports if name == forbidden_prefix or name.startswith(f"{forbidden_prefix}."))
        assert violations == [], f"{path.relative_to(PROJECT_ROOT)} imports HTTP schemas: {violations}"
