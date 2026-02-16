"""Self-evolution engine — enables the agent to create and register new tools dynamically."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

from spot_agent.logging import get_logger
from spot_agent.tools.base import BaseTool
from spot_agent.tools.registry import ToolRegistry

log = get_logger(__name__)


class SelfEvolutionEngine:
    """Enables the agent to evolve by creating new tools and improving capabilities."""

    def __init__(self, plugins_dir: str, registry: ToolRegistry) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self._loaded_plugins: dict[str, str] = {}  # name -> file path

    def load_existing_plugins(self) -> int:
        """Load all existing plugins from the plugins directory."""
        loaded = 0
        for plugin_file in self.plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            try:
                self._load_plugin_file(plugin_file)
                loaded += 1
            except Exception as exc:
                log.error("plugin_load_failed", file=str(plugin_file), error=str(exc))
        log.info("plugins_loaded", count=loaded)
        return loaded

    def _load_plugin_file(self, plugin_path: Path) -> None:
        """Dynamically load a plugin file and register its tools."""
        module_name = f"spot_agent.plugins.{plugin_path.stem}"

        spec = importlib.util.spec_from_file_location(module_name, str(plugin_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load plugin: {plugin_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find and register all BaseTool subclasses in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseTool)
                and attr is not BaseTool
            ):
                try:
                    tool = attr()
                    self.registry.register(tool)
                    self._loaded_plugins[tool.name] = str(plugin_path)
                    log.info("plugin_tool_registered", tool=tool.name, file=str(plugin_path))
                except Exception as exc:
                    log.error("plugin_instantiation_failed", class_name=attr_name, error=str(exc))

    async def create_tool(self, tool_name: str, tool_description: str, tool_code: str) -> dict[str, Any]:
        """Create a new tool plugin from generated code.
        
        Args:
            tool_name: Name for the new tool
            tool_description: Description of what the tool does
            tool_code: Python source code implementing the tool as a BaseTool subclass
            
        Returns:
            dict with success status and details
        """
        # Sanitize tool name for filename
        safe_name = tool_name.replace("-", "_").replace(" ", "_").lower()
        plugin_path = self.plugins_dir / f"{safe_name}.py"

        # Write the plugin file
        try:
            plugin_path.write_text(tool_code, encoding="utf-8")
            log.info("plugin_file_created", path=str(plugin_path))
        except Exception as exc:
            return {"success": False, "error": f"Failed to write plugin: {exc}"}

        # Attempt to load it
        try:
            self._load_plugin_file(plugin_path)
            return {
                "success": True,
                "tool_name": tool_name,
                "plugin_path": str(plugin_path),
                "message": f"Tool '{tool_name}' created and registered successfully",
            }
        except Exception as exc:
            # Remove the broken plugin file
            plugin_path.unlink(missing_ok=True)
            return {"success": False, "error": f"Plugin failed to load: {exc}"}

    async def remove_tool(self, tool_name: str) -> dict[str, Any]:
        """Remove a dynamically created tool."""
        if tool_name not in self._loaded_plugins:
            return {"success": False, "error": f"Tool '{tool_name}' is not a dynamic plugin"}

        plugin_path = Path(self._loaded_plugins[tool_name])
        self.registry.unregister(tool_name)
        plugin_path.unlink(missing_ok=True)
        del self._loaded_plugins[tool_name]

        log.info("plugin_removed", tool=tool_name)
        return {"success": True, "message": f"Tool '{tool_name}' removed"}

    def list_plugins(self) -> list[dict[str, str]]:
        """List all loaded plugins."""
        return [
            {"name": name, "path": path}
            for name, path in self._loaded_plugins.items()
        ]
