import PySimpleGUI as sg
from utils.db_utils import DBManager
import typing as t
from utils.bw_fetcher import BimmerWorkFetcher, FetchException


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


def run_main_window(db: DBManager) -> None:
    window_main = launch_main_window()

    while True:
        event_main, values_main = window_main.read()
        if event_main in (sg.WIN_CLOSED, "Exit"):
            break

        elif event_main == "Manual Vehicle Import":
            run_manual_import_window(db)

        elif event_main == "Automated Vehicle Import":
            run_auto_import_window(db)

        elif event_main == "Browse Vehicle Database":
            code_type = run_model_selector_window(db)
            if not code_type:
                continue
            run_browser_window(code_type, db)

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


def run_manual_import_window(db: DBManager) -> None:
    window_mvi = launch_manual_import_window()
    while True:
        event_mvi, values_mvi = window_mvi.read()
        if event_mvi in (sg.WIN_CLOSED, "Exit"):
            break
        elif event_mvi == "Import Vehicle Data":
            data = [
                tuple(line.split("\t"))
                for line in values_mvi["-MANUAL_IMPORT_INPUT-"].split("\n")
                if line and line.count("\t") > 0
            ]
            window_mvi["-MANUAL_IMPORT_OUTPUT-"].update(db.import_vehicle(data))

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


def run_auto_import_window(db: DBManager) -> None:
    window_avi = launch_auto_import_window()
    fetcher = None
    while True:
        event_avi, values_avi = window_avi.read(timeout=200)
        if event_avi in (sg.WIN_CLOSED, "Exit"):
            break

        elif event_avi == "Import Vehicle Data":
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


def run_model_selector_window(db: DBManager) -> t.Optional[str]:
    window_ms = launch_model_selector_window(db.get_all_code_types())
    code_type = None
    while True:
        event_ms, values_ms = window_ms.read()
        if event_ms in (sg.WIN_CLOSED, "Exit"):
            break
        elif event_ms == "Select" and values_ms["-MODEL_SELECTOR_LISTBOX-"]:
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
            sg.Button("Allow Selected"),
            sg.Button("Disallow Selected"),
            sg.Button("Reset Selected"),
            sg.Button("Reset All"),
        ],
    ]

    viewer_column_layout = [
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


def run_browser_window(code_type: str, db: DBManager) -> None:
    exclude_options = set()
    include_options = set()
    vehicle_data = db.search_vehicles(code_type)
    options_mapping = db.get_option_mapping(code_type)
    window_br = launch_browser_window(code_type, vehicle_data, options_mapping)
    while True:
        event_br, values_br = window_br.read()
        if event_br in (sg.WIN_CLOSED, "Exit"):
            break

        # Events which require refreshing the browser treedata
        elif event_br in (
            "Allow Selected",
            "Disallow Selected",
            "Reset Selected",
            "Reset All",
            "Delete Selected Vehicles",
        ):
            changeset = set(o[0] for o in values_br["-BROWSER_OPTIONS_LISTBOX-"])
            if event_br == "Reset Selected":
                exclude_options -= changeset
                include_options -= changeset
            elif event_br == "Disallow Selected":
                include_options -= changeset
                exclude_options = exclude_options | changeset
            elif event_br == "Allow Selected":
                exclude_options -= changeset
                include_options = include_options | changeset
            elif event_br == "Reset All":
                exclude_options = set()
                include_options = set()
            elif event_br == "Delete Selected Vehicles":
                db.delete_vehicles([i[1:-1] for i in values_br["-BROWSER_TREE-"]])

            vehicle_data = db.search_vehicles(
                code_type, exclude_options, include_options
            )
            new_treedata = build_browser_treedata(vehicle_data, options_mapping)
            window_br["-BROWSER_TREE-"].update(values=new_treedata)
            window_br["-BROWSER_OPTIONS_LISTBOX-"].update(set_to_index=[])
            for i, item in enumerate(
                window_br["-BROWSER_OPTIONS_LISTBOX-"].get_list_values()
            ):
                if item[0] in include_options:
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
                    )
            else:
                treedata.Insert(f"_{car['vin']}_", f"_{car['vin']}_{key}_", key, [val])
    return treedata


def main():
    db = DBManager()
    run_main_window(db)
    db.close()


if __name__ == "__main__":
    main()
