# ParameterSweepExporter – Fusion 360 Add-In
# Entry point: registers the command in the toolbar and delegates to the sweep logic.

import adsk.core
import adsk.fusion
import traceback
import importlib
import os

# Global references kept alive for the duration of the session.
_app: adsk.core.Application = None
_ui: adsk.core.UserInterface = None
_handlers = []

CMD_ID = "paramSweepExporterCmd"
CMD_NAME = "Parameter Sweep Exporter"
CMD_DESCRIPTION = "Batch-export a parameterized model by sweeping parameter ranges."
PANEL_ID = "SolidScriptsAddinsPanel"

# ---------------------------------------------------------------------------
# Command Created handler – builds the UI and wires events
# ---------------------------------------------------------------------------
class SweepCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            from . import sweep_logic
            importlib.reload(sweep_logic)  # force reload so edits take effect
            sweep_logic.on_command_created(args, _handlers)
        except Exception:
            if _ui:
                _ui.messageBox(f"Error in CommandCreated:\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Add-in lifecycle
# ---------------------------------------------------------------------------
def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

        cmd_def = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESCRIPTION,
            ""  # no custom icon folder
        )

        on_created = SweepCommandCreatedHandler()
        cmd_def.commandCreated.add(on_created)
        _handlers.append(on_created)

        # Add to the ADD-INS panel in the TOOLS tab
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel:
            existing = panel.controls.itemById(CMD_ID)
            if not existing:
                panel.controls.addCommand(cmd_def)

        # Also make it available immediately while debugging
        # cmd_def.execute()  # Uncomment to auto-launch on run

    except Exception:
        if _ui:
            _ui.messageBox(f"Failed to start add-in:\n{traceback.format_exc()}")


def stop(context):
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel:
            ctrl = panel.controls.itemById(CMD_ID)
            if ctrl:
                ctrl.deleteMe()
    except Exception:
        if _ui:
            _ui.messageBox(f"Failed to stop add-in:\n{traceback.format_exc()}")
