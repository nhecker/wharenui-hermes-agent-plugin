from hermes_cli.plugins import get_plugin_manager, PluginContext, PluginManifest
from wharenui_plugin import register
mgr = get_plugin_manager()
manifest = PluginManifest(name="wharenui", key="wharenui", version="0.1.0", path="/tmp")
ctx = PluginContext(manifest, mgr)
import wharenui_plugin
ctx.plugin_module = wharenui_plugin
register(ctx)

from hermes_cli.plugins import get_control_tool_names
print("CONTROL TOOL NAMES:", get_control_tool_names())
