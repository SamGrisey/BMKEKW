# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring
import typing as t
from contextlib import contextmanager
import PySimpleGUI as sg
from utils.db_utils import DBManager
from utils.bw_fetcher import BimmerWorkFetcher

CHECK_MARK_ICON = b"iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAABgUExURV16RpGYjH6TbXGLXM3mucLmqajld1KCLIvSWIPNU4DLT5PmV1JnQpHQaYvOYDZZGrPdluz35f///0twLtTtxYzlUHG/RHbDR/n894nkTKTad2m4PkxgPH7VR4DZSAAAALbJwFUAAAAgdFJOU/////////////////////////////////////////8AXFwb7QAAAAlwSFlzAAAOwwAADsMBx2+oZAAAAIdJREFUKFNdzNESwxAQBdBIpAm6GipURf3/X2YXnXZyH4x7dhnKJRUGxtg4thmdE+fzDbN0mPiKEUIqkqHcORYhJXCtHhU2mkowFtSzAS1oY53YO2hnwNnNh70/gfllsP8gBDDYvY8N3ikEqim1jXKseKdE/JMAJeacP7VXKMdCwf0v/OcCpZycmhXp7UdT0gAAAABJRU5ErkJggg=="  # pylint: disable=line-too-long
BLANK_ICON = b"iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsIAAA7CARUoSoAAAAATSURBVDhPYxgFo2AUjAIwYGAAAAQQAAGnRHxjAAAAAElFTkSuQmCC"  # pylint: disable=line-too-long


@contextmanager
def hide_window_for_context(caller: sg.Window):
    try:
        caller.Hide()
        yield None
    finally:
        caller.UnHide()


def launch_main_window() -> sg.Window:
    main_screen_layout = [
        [
            sg.Button("Browse Vehicle Database"),
        ],
        [
            sg.Button("Manual Vehicle Import"),
        ],
        [
            sg.Button("Automated Vehicle Import"),
        ],
        [
            sg.Button("Exit"),
        ],
    ]

    return sg.Window(
        "BMKEKW",
        main_screen_layout,
        grab_anywhere_using_control=False,
        element_justification="center",
    )


def run_main_window(db_: DBManager) -> None:
    window_main = launch_main_window()

    while True:
        event_main, _ = window_main.read()
        if event_main in (sg.WIN_CLOSED, "Exit"):
            break

        if event_main == "Manual Vehicle Import":
            with hide_window_for_context(window_main):
                run_manual_import_window(db_)

        elif event_main == "Automated Vehicle Import":
            with hide_window_for_context(window_main):
                run_auto_import_window()

        elif event_main == "Browse Vehicle Database":
            code_type = run_model_selector_window(db_)
            if not code_type:
                continue
            with hide_window_for_context(window_main):
                run_browser_window(code_type, db_)

    window_main.close()


def launch_manual_import_window() -> sg.Window:
    manual_vehicle_import_layout = [
        [
            sg.Text(
                "The manual import tool is designed to parse the page content "
                "of bimmer.work. Look up a vehicle onsite, then press ctrl+a, ctrl+c "
                "to copy the page content and paste it below.",
                size=(90, 3),
            )
        ],
        [sg.Multiline("", size=(100, 25), key="-MANUAL_IMPORT_INPUT-")],
        [sg.Text(size=(90, 1), key="-MANUAL_IMPORT_OUTPUT-")],
        [sg.Button("Import Vehicle Data"), sg.Button("Exit")],
    ]

    return sg.Window(
        "BMKEKW - Manual Vehicle Import",
        manual_vehicle_import_layout,
        grab_anywhere_using_control=False,
    )


def run_manual_import_window(db_: DBManager) -> None:
    window_mvi = launch_manual_import_window()
    while True:
        event_mvi, values_mvi = window_mvi.read()
        if event_mvi in (sg.WIN_CLOSED, "Exit"):
            break
        if event_mvi == "Import Vehicle Data":
            data = [
                tuple(line.split("\t"))
                for line in values_mvi["-MANUAL_IMPORT_INPUT-"].split("\n")
                if line and line.count("\t") > 0
            ]
            window_mvi["-MANUAL_IMPORT_OUTPUT-"].update(db_.import_vehicle(data))

    window_mvi.close()


def launch_auto_import_window() -> sg.Window:
    auto_vehicle_import_layout = [
        [
            sg.Text(
                "The automated import tool uses the selenium webdriver to pull vehicle "
                "data from bimmer.work. The site is protected by a captcha thus the success "
                "rate is ~20% and can take up to 45sec per vin. Manual import is strongly "
                "recommended for now. Enter vins below separated by commas. The auto import "
                "process may briefly appear to be unresponsive.",
                size=(90, 3),
            )
        ],
        [sg.Multiline("", size=(100, 3), key="-AUTO_IMPORT_INPUT-")],
        [sg.Text(size=(90, 10), key="-AUTO_IMPORT_OUTPUT-")],
        [
            sg.Button("Import Vehicle Data"),
            sg.ProgressBar(
                max_value=100, style="winnative", key="-AUTO_IMPORT_PROGRESS-"
            ),
            sg.Button("Exit"),
        ],
    ]

    return sg.Window(
        "BMKEKW - Automated Vehicle Import",
        auto_vehicle_import_layout,
        grab_anywhere_using_control=False,
    )


def run_auto_import_window() -> None:
    window_avi = launch_auto_import_window()
    fetcher = None
    while True:
        event_avi, values_avi = window_avi.read(timeout=200)
        if event_avi in (sg.WIN_CLOSED, "Exit"):
            break

        if event_avi == "Import Vehicle Data":
            if not fetcher:
                fetcher = BimmerWorkFetcher()
            if not fetcher.task_running():
                vins = values_avi["-AUTO_IMPORT_INPUT-"].split(",")
                fetcher.start_import_task(vins)

        if fetcher and fetcher.task_running():
            window_avi["-AUTO_IMPORT_PROGRESS-"].update(
                current_count=fetcher.task_progress(),
            )

            if fetcher.task_progress() == 100:
                window_avi["-AUTO_IMPORT_OUTPUT-"].update(
                    "\n".join(fetcher.consume_task_results())
                )

    if fetcher:
        fetcher.close()
    window_avi.close()


def launch_model_selector_window(models: t.List[str]) -> sg.Window:
    model_selector_layout = [
        [
            sg.Listbox(
                values=models,
                size=(30, 6),
                key="-MODEL_SELECTOR_LISTBOX-",
                bind_return_key=True,
            )
        ],
        [sg.Button("Select"), sg.Button("Exit")],
    ]

    return sg.Window(
        "BMKEKW - Model Selector",
        model_selector_layout,
        grab_anywhere_using_control=False,
    )


def run_model_selector_window(db_: DBManager) -> t.Optional[str]:
    window_ms = launch_model_selector_window(db_.get_all_code_types())
    code_type = None
    while True:
        event_ms, values_ms = window_ms.read()
        if event_ms in (sg.WIN_CLOSED, "Exit"):
            break
        if event_ms == "Select" and values_ms["-MODEL_SELECTOR_LISTBOX-"]:
            code_type = values_ms["-MODEL_SELECTOR_LISTBOX-"][0]
            break

    window_ms.close()
    return code_type


def launch_browser_window(
    code_type: str,
    vehicles: t.List[t.Dict[str, t.Any]],
    options_mapping: t.Dict[str, str],
) -> sg.Window:
    treedata = build_browser_treedata(vehicles, options_mapping)

    filter_column_layout = [
        [
            sg.Listbox(
                values=list(options_mapping.items()),
                size=(60, 40),
                select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE,
                key="-BROWSER_OPTIONS_LISTBOX-",
            ),
        ],
        [
            sg.Button("Require Selected"),
            sg.Button("Disallow Selected"),
            sg.Button("Reset Selected"),
            sg.Button("Reset All"),
        ],
    ]

    viewer_column_layout = [
        [
            sg.Text(
                "Check mark indicates an option missing from at least 1 other displayed vehicle.",
                size=(90, 1),
            )
        ],
        [
            sg.Tree(
                data=treedata,
                headings=[""],
                col0_width=40,
                num_rows=40,
                key="-BROWSER_TREE-",
                expand_x=True,
                expand_y=True,
            ),
        ],
        [
            sg.Button("Delete Selected Vehicles"),
        ],
    ]

    browser_layout = [
        [
            sg.Column(filter_column_layout),
            sg.VerticalSeparator(),
            sg.Column(viewer_column_layout),
        ],
        [sg.HorizontalSeparator()],
        [sg.Button("Exit")],
    ]

    return sg.Window(
        f"BMKEKW - Browser: {code_type}",
        browser_layout,
        grab_anywhere_using_control=False,
    )


def run_browser_window(  # pylint: disable=too-many-branches
    code_type: str, db_: DBManager
) -> None:
    exclude_options = set()
    require_options = set()
    vehicle_data = db_.search_vehicles(code_type)
    options_mapping = db_.get_option_mapping(code_type)
    window_br = launch_browser_window(code_type, vehicle_data, options_mapping)
    while True:
        event_br, values_br = window_br.read()
        if event_br in (sg.WIN_CLOSED, "Exit"):
            break

        # Events which require refreshing the browser treedata
        if event_br in (
            "Require Selected",
            "Disallow Selected",
            "Reset Selected",
            "Reset All",
            "Delete Selected Vehicles",
        ):
            changeset = set(o[0] for o in values_br["-BROWSER_OPTIONS_LISTBOX-"])
            if event_br == "Reset Selected":
                exclude_options -= changeset
                require_options -= changeset
            elif event_br == "Disallow Selected":
                require_options -= changeset
                exclude_options = exclude_options | changeset
            elif event_br == "Require Selected":
                exclude_options -= changeset
                require_options = require_options | changeset
            elif event_br == "Reset All":
                exclude_options = set()
                require_options = set()
            elif event_br == "Delete Selected Vehicles":
                if (
                    sg.popup_yes_no(
                        "Do you really want to delete the selected vehicle(s)?"
                    )
                    == "Yes"
                ):
                    db_.delete_vehicles([i[1:-1] for i in values_br["-BROWSER_TREE-"]])

            vehicle_data = db_.search_vehicles(
                code_type, exclude_options, require_options
            )
            new_treedata = build_browser_treedata(vehicle_data, options_mapping)
            window_br["-BROWSER_TREE-"].update(values=new_treedata)
            window_br["-BROWSER_OPTIONS_LISTBOX-"].update(set_to_index=[])
            for i, item in enumerate(
                window_br[  # pylint: disable=no-member
                    "-BROWSER_OPTIONS_LISTBOX-"
                ].get_list_values()
            ):
                if item[0] in require_options:
                    window_br["-BROWSER_OPTIONS_LISTBOX-"].Widget.itemconfigure(
                        i, bg="green", fg="white"
                    )
                elif item[0] in exclude_options:
                    window_br["-BROWSER_OPTIONS_LISTBOX-"].Widget.itemconfigure(
                        i, bg="red", fg="white"
                    )
                else:
                    window_br["-BROWSER_OPTIONS_LISTBOX-"].Widget.itemconfigure(
                        i, bg="", fg=""
                    )

    window_br.close()


def build_browser_treedata(
    vehicles: t.List[t.Dict[str, t.Any]],
    options_mapping: t.Dict[str, str],
) -> sg.TreeData:
    # build set of options missing from at least 1 car in vehicles
    universe = set(options_mapping.keys())
    missing_opts = set().union(*[universe - set(car["options"]) for car in vehicles])

    treedata = sg.TreeData()
    for car in vehicles:
        treedata.Insert("", f"_{car['vin']}_", car["vin"], [])
        for key, val in car.items():
            if key == "options":
                treedata.Insert(f"_{car['vin']}_", f"_{car['vin']}_{key}_", key, [])
                for option in val:
                    treedata.Insert(
                        f"_{car['vin']}_{key}_",
                        f"_{car['vin']}_{key}_{option}_",
                        option,
                        [options_mapping[option]],
                        icon=CHECK_MARK_ICON if option in missing_opts else BLANK_ICON,
                    )
            else:
                treedata.Insert(f"_{car['vin']}_", f"_{car['vin']}_{key}_", key, [val])
    return treedata


def main():
    db_ = DBManager()
    run_main_window(db_)
    db_.close()


if __name__ == "__main__":
    main()
