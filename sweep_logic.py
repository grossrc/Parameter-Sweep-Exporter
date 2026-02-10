# sweep_logic.py – Core sweep + export logic for ParameterSweepExporter
#
# This module is imported by the add-in entry point.  It owns:
#   • Building the native Fusion command inputs (parameter table, range
#     entries, body/component selection, export format, output folder).
#   • Computing the full combinatorial sweep.
#   • Driving the timeline, updating parameters, and exporting files.

from __future__ import annotations

import adsk.core
import adsk.fusion
import itertools
import json
import math
import os
import re
import traceback
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _float_range(low: float, high: float, steps: int) -> List[float]:
    """Return *steps* evenly-spaced values from *low* to *high* inclusive."""
    if steps < 1:
        return []
    if steps == 1:
        return [low]
    return [low + i * (high - low) / (steps - 1) for i in range(steps)]


def _sanitize(name: str) -> str:
    """Strip characters that are unsafe for file names."""
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def _format_value(val: float) -> str:
    """Compact number string – drop trailing zeros."""
    s = f"{val:.6f}".rstrip("0").rstrip(".")
    return s


def _collect_all_parameters(design: adsk.fusion.Design):
    """Return a list of dicts for favorited parameters in the active design.

    Values are converted from internal units (cm/rad) to the parameter's
    display unit so the UI shows the correct numbers.
    """
    params = []
    try:
        plist = design.allParameters
        count = plist.count
    except Exception:
        return params

    um = design.unitsManager

    for i in range(count):
        try:
            p = plist.item(i)
            name = p.name
        except Exception:
            continue

        # Only include favorited parameters
        try:
            is_fav = p.isFavorite
        except Exception:
            is_fav = False
        if not is_fav:
            continue

        try:
            expression = p.expression
        except Exception:
            expression = ""
        try:
            raw_value = p.value
        except Exception:
            raw_value = 0.0
        try:
            unit = p.unit
        except Exception:
            unit = ""

        # Convert internal value to display units
        try:
            if unit:
                display_value = um.convert(raw_value, um.internalUnits, unit)
            else:
                display_value = raw_value
        except Exception:
            display_value = raw_value

        try:
            is_user = p.objectType == adsk.fusion.UserParameter.classType()
        except Exception:
            is_user = False

        params.append({
            "name": name,
            "expression": expression,
            "value": display_value,
            "unit": unit,
            "isFavorite": is_fav,
            "isUserParam": is_user,
        })
    return params


def _collect_all_bodies(design: adsk.fusion.Design):
    """Walk the component tree and return [(body, component, path)] for every
    BRepBody in the design.  Uses indexed access for reliability."""
    results = []

    def _walk(occ_path: str, comp: adsk.fusion.Component):
        try:
            body_list = comp.bRepBodies
            for i in range(body_list.count):
                body = body_list.item(i)
                full = f"{occ_path}/{body.name}" if occ_path else body.name
                results.append((body, comp, full))
        except Exception:
            pass
        try:
            occs = comp.occurrences
            for i in range(occs.count):
                occ = occs.item(i)
                child_path = f"{occ_path}/{occ.name}" if occ_path else occ.name
                _walk(child_path, occ.component)
        except Exception:
            pass

    _walk("", design.rootComponent)
    return results


# ---------------------------------------------------------------------------
# Palette / HTML-based command (simpler & more flexible than table inputs)
# ---------------------------------------------------------------------------
# We use a *Command* with a custom HTML palette so the user gets a nice
# scrollable list of parameters + bodies to select.

PALETTE_ID = "paramSweepPalette"
PALETTE_TITLE = "Parameter Sweep Exporter"
PALETTE_URL = ""  # set at runtime to point to the local HTML file
PALETTE_WIDTH = 720
PALETTE_HEIGHT = 700

_palette: adsk.core.Palette = None
_cached_config: dict = None  # filled by the palette before OK


class _PaletteHTMLHandler(adsk.core.HTMLEventHandler):
    """Handles messages sent from the palette HTML page via
    ``adsk.fusionSendData(action, data)``."""

    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.HTMLEventArgs):
        global _cached_config
        try:
            action = args.action
            data = args.data

            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)

            if action == "ready":
                if not design:
                    args.returnData = json.dumps({
                        "parameters": [],
                        "bodies": [],
                        "error": "No active Fusion design found.",
                    })
                    return

                # Page loaded – send parameter + body info to the page.
                params = _collect_all_parameters(design)
                bodies = _collect_all_bodies(design)

                payload = json.dumps({
                    "parameters": params,
                    "bodies": [
                        {"path": path, "name": body.name}
                        for body, comp, path in bodies
                    ],
                })
                args.returnData = payload

            elif action == "browse":
                # Open native folder dialog
                folder_dlg = ui.createFolderDialog()
                folder_dlg.title = "Select Output Folder"
                result = folder_dlg.showDialog()
                if result == adsk.core.DialogResults.DialogOK:
                    args.returnData = json.dumps({"folder": folder_dlg.folder})
                else:
                    args.returnData = json.dumps({"folder": ""})

            elif action == "submit":
                # User clicked Export – stash configuration and close palette.
                _cached_config = json.loads(data)
                palette = ui.palettes.itemById(PALETTE_ID)
                if palette:
                    palette.isVisible = False
                # Trigger the actual export
                _run_export(ui, design, _cached_config)

            elif action == "cancel":
                palette = ui.palettes.itemById(PALETTE_ID)
                if palette:
                    palette.isVisible = False

        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f"Palette handler error:\n{traceback.format_exc()}"
            )


class _PaletteCloseHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        pass  # nothing to clean up


# ---------------------------------------------------------------------------
# Public entry point – called from CommandCreated in the main script
# ---------------------------------------------------------------------------

def on_command_created(args: adsk.core.CommandCreatedEventArgs, handlers: list):
    """Build and display the palette-based UI."""
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = adsk.fusion.Design.cast(app.activeProduct)

    if not design:
        ui.messageBox("No active Fusion design. Please open a design first.")
        return

    # Resolve path to our HTML file (add cache-bust so Fusion reloads changes)
    html_path = os.path.join(os.path.dirname(__file__), "palette.html")
    import time
    html_url = f"file:///{html_path.replace(os.sep, '/')}?v={int(time.time())}"

    # Delete old palette if it exists
    old = ui.palettes.itemById(PALETTE_ID)
    if old:
        old.deleteMe()

    palette = ui.palettes.add(
        PALETTE_ID,
        PALETTE_TITLE,
        html_url,
        True,   # isVisible
        True,   # showCloseButton
        True,   # isResizable
        PALETTE_WIDTH,
        PALETTE_HEIGHT,
        True,   # useNewWebBrowser
    )
    palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateFloating

    # Wire up event handlers
    html_handler = _PaletteHTMLHandler()
    palette.incomingFromHTML.add(html_handler)
    handlers.append(html_handler)

    close_handler = _PaletteCloseHandler()
    palette.closed.add(close_handler)
    handlers.append(close_handler)

    # We don't actually need the Command to have its own dialog – cancel it
    # so Fusion doesn't show an empty command dialog.
    args.command.isOKButtonVisible = False
    cancel_handler = _CommandDestroyHandler()
    args.command.destroy.add(cancel_handler)
    handlers.append(cancel_handler)

    # Auto-execute immediately so the command dialog doesn't hang around
    args.command.isAutoExecute = True


class _CommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        pass


# ---------------------------------------------------------------------------
# Export engine
# ---------------------------------------------------------------------------

def _run_export(ui: adsk.core.UserInterface, design: adsk.fusion.Design,
                config: dict):
    """Execute the full combinatorial sweep + export."""
    try:
        output_folder: str = config.get("outputFolder", "")
        export_format: str = config.get("format", "STEP").upper()
        selected_params: list = config.get("params", [])
        selected_body_paths: list = config.get("bodies", [])
        naming_template: str = config.get("namingTemplate", "")

        if not output_folder:
            ui.messageBox("No output folder selected. Aborting.")
            return
        if not selected_params:
            ui.messageBox("No parameters selected. Aborting.")
            return

        # Build the axis values for each parameter
        axes: List[Tuple[str, List[float], str]] = []
        for sp in selected_params:
            name = sp["name"]
            low = float(sp["low"])
            high = float(sp["high"])
            steps = int(sp["steps"])
            unit = sp.get("unit", "")
            vals = _float_range(low, high, steps)
            axes.append((name, vals, unit))

        # Cartesian product of all axes
        all_combos = list(itertools.product(*[vals for _, vals, _ in axes]))
        total = len(all_combos)

        if total == 0:
            ui.messageBox("No combinations to export.")
            return

        confirm = ui.messageBox(
            f"This will export {total} file(s) to:\n{output_folder}\n\nContinue?",
            "Confirm Export",
            adsk.core.MessageBoxButtonTypes.YesNoButtonType,
        )
        if confirm != adsk.core.DialogResults.DialogYes:
            return

        # Resolve body references (match by path string)
        all_bodies = _collect_all_bodies(design)
        export_bodies = []
        if selected_body_paths:
            path_set = set(selected_body_paths)
            for body, comp, path in all_bodies:
                if path in path_set:
                    export_bodies.append((body, comp, path))
        else:
            export_bodies = all_bodies  # export everything

        if not export_bodies:
            ui.messageBox("No matching bodies found. Aborting.")
            return

        # Grab all parameters by name for quick access
        all_params: Dict[str, adsk.fusion.Parameter] = {}
        for p in design.allParameters:
            all_params[p.name] = p

        # Store original values so we can restore them at the end
        original_expressions: Dict[str, str] = {}
        for name, _, _ in axes:
            if name in all_params:
                original_expressions[name] = all_params[name].expression

        progress = ui.createProgressDialog()
        progress.show("Exporting…", f"0 / {total}", 0, total, 1)

        export_mgr = design.exportManager
        errors = []

        for idx, combo in enumerate(all_combos):
            if progress.wasCancelled:
                break

            # --- update parameters ---
            for (param_name, _, unit), value in zip(axes, combo):
                p = all_params.get(param_name)
                if p:
                    # Build expression with unit, e.g. "1.5 mm"
                    expr = f"{_format_value(value)} {unit}" if unit else _format_value(value)
                    p.expression = expr

            # Force a recompute so geometry updates
            adsk.doEvents()
            design.rootComponent.isSketchFolderLightBulbOn = True  # prod recompute
            adsk.doEvents()

            # --- build file name ---
            parts = []
            for (param_name, _, _), value in zip(axes, combo):
                parts.append(f"{param_name}_{_format_value(value)}")
            base_name = _sanitize("__".join(parts))

            if naming_template:
                # Allow a user template like "{PlateThickness}_{WallHeight}"
                tpl_name = naming_template
                for (param_name, _, _), value in zip(axes, combo):
                    tpl_name = tpl_name.replace(
                        f"{{{param_name}}}", _format_value(value)
                    )
                base_name = _sanitize(tpl_name)

            # --- export ---
            try:
                if export_format == "STL":
                    _export_stl(export_mgr, export_bodies, output_folder,
                                base_name, design)
                else:
                    _export_step(export_mgr, output_folder, base_name, design)
            except Exception as ex:
                errors.append(f"Combo {idx+1}: {ex}")

            progress.progressValue = idx + 1
            progress.message = f"{idx + 1} / {total}"
            adsk.doEvents()

        progress.hide()

        # --- restore original parameter values ---
        for name, expr in original_expressions.items():
            p = all_params.get(name)
            if p:
                p.expression = expr
        adsk.doEvents()

        # Summary
        if errors:
            ui.messageBox(
                f"Export complete with {len(errors)} error(s):\n\n"
                + "\n".join(errors[:20])
            )
        else:
            ui.messageBox(
                f"Successfully exported {total} file(s) to:\n{output_folder}"
            )

    except Exception:
        ui.messageBox(f"Export error:\n{traceback.format_exc()}")


def _export_step(export_mgr, output_folder, base_name, design):
    """Export the entire design (or active bodies) as a STEP file."""
    filepath = os.path.join(output_folder, f"{base_name}.step")
    options = export_mgr.createSTEPExportOptions(filepath)
    export_mgr.execute(options)


def _export_stl(export_mgr, bodies, output_folder, base_name, design):
    """Export each selected body as an STL (combined into one if multiple)."""
    if len(bodies) == 1:
        body, comp, path = bodies[0]
        filepath = os.path.join(output_folder, f"{base_name}.stl")
        options = export_mgr.createSTLExportOptions(body, filepath)
        options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementMedium
        export_mgr.execute(options)
    else:
        # Export each body individually with its name appended
        for body, comp, path in bodies:
            body_label = _sanitize(body.name)
            filepath = os.path.join(
                output_folder, f"{base_name}__{body_label}.stl"
            )
            options = export_mgr.createSTLExportOptions(body, filepath)
            options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementMedium
            export_mgr.execute(options)
