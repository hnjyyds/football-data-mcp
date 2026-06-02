from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Iterable
from typing import Any, Protocol, cast


DEFAULT_CONTROLLERS_PACKAGE = "football_data_mcp.api.controllers"
RouteHandler = Callable[..., Any]


class SupportsCustomRoute(Protocol):
    def custom_route(
        self,
        path: str,
        *,
        methods: list[str],
        include_in_schema: bool,
    ) -> Callable[[RouteHandler], RouteHandler]:
        ...


def iter_controller_module_names(package_name: str = DEFAULT_CONTROLLERS_PACKAGE) -> Iterable[str]:
    """Discover controller modules without a hand-maintained import list."""
    package = importlib.import_module(package_name)
    package_path = getattr(package, "__path__", None)
    if package_path is None:
        return []
    return (
        f"{package_name}.{module_info.name}"
        for module_info in sorted(pkgutil.iter_modules(package_path), key=lambda item: item.name)
        if not module_info.ispkg and not module_info.name.startswith("_")
    )


def register_controllers(mcp: Any, *, package_name: str = DEFAULT_CONTROLLERS_PACKAGE) -> list[dict[str, Any]]:
    """Register every controller that exposes ``register(mcp)``.

    The return value is intentionally simple so tests and the Project endpoint
    can show exactly which controllers contributed routes.
    """
    registrations: list[dict[str, Any]] = []
    for module_name in iter_controller_module_names(package_name):
        module = importlib.import_module(module_name)
        register = getattr(module, "register", None)
        if not callable(register):
            continue
        routes_value = cast(Iterable[dict[str, Any]] | None, register(mcp))
        routes = list(routes_value or [])
        registrations.append({"module": module_name, "routes": routes})
    return registrations
