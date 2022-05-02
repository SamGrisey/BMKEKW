# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring
import typing as t
import sqlite3
from json import dumps, loads
import re

VEHICLES_TABLE_SCHEMA = """
CREATE TABLE vehicles(
    vin TEXT PRIMARY KEY,
    code_type TEXT,
    color TEXT,
    upholstery TEXT,
    production_date TEXT,
    options TEXT
)
"""

OPTIONS_TABLE_SCHEMA = """
CREATE TABLE options(
    id TEXT,
    code_type TEXT,
    name TEXT,
    PRIMARY KEY (id, code_type)
)
"""


def regexp(expr, item):
    reg = re.compile(expr)
    return reg.search(item) is not None


class DBManager:
    def __init__(self):
        self._conn = sqlite3.connect("bmkekw.db")
        self._conn.create_function("REGEXP", 2, regexp)

        # init tables if they dont exist
        options_exists = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='options'"
        ).fetchall()
        if not options_exists:
            self._conn.execute(OPTIONS_TABLE_SCHEMA)

        vehicles_exists = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vehicles'"
        ).fetchall()
        if not vehicles_exists:
            self._conn.execute(VEHICLES_TABLE_SCHEMA)

        if self._conn.in_transaction:
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _update_options_mapping(
        self, code_type: str, mapping: t.Dict[str, str]
    ) -> None:
        records = [(id, code_type, name) for id, name in mapping.items()]
        self._conn.executemany(
            "INSERT OR IGNORE INTO options VALUES (?, ?, ?)", records
        )
        if self._conn.in_transaction:
            self._conn.commit()

    def _insert_vehicle(self, vehicle_record: t.Tuple[t.Any, ...]) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO vehicles VALUES (?, ?, ?, ?, ?, ?)", vehicle_record
        )
        if self._conn.in_transaction:
            self._conn.commit()

    def import_vehicle(self, data: t.List[t.Tuple[str, ...]]) -> str:
        vin = ""
        code_type = ""
        color = ""
        upholstery = ""
        production_date = ""
        options = []
        options_mapping = {}

        if not data:
            return "No data supplied"

        for key, value, *_ in data:
            if key == "VIN":
                vin = value
            elif key == "Code / Type":
                code_type = value
            elif key == "Color":
                color = value
            elif key == "Upholstery":
                upholstery = value
            elif key == "Production Date":
                production_date = value
            elif re.fullmatch(r"[\w\d]{3}", key):
                options.append(key)
                options_mapping[key] = value

        if any(
            not x for x in (vin, code_type, color, upholstery, production_date, options)
        ):
            return "Insufficient data supplied"

        # options must be sorted since SQLite doesn't support arrays or the ALL operator
        # so we must use regex for requiring a set of options
        options.sort()
        self._update_options_mapping(code_type, options_mapping)
        self._insert_vehicle(
            (vin, code_type, color, upholstery, production_date, dumps(options))
        )

        return "Import complete"

    def search_vehicles(
        self,
        code_type: str,
        exclude_options: t.Optional[t.Set[str]] = None,
        include_options: t.Optional[t.Set[str]] = None,
    ) -> t.List[t.Dict[str, t.Any]]:
        where_clause = ""
        kwargs = {"ct": code_type}
        if exclude_options:
            where_clause += " AND NOT options REGEXP :eo"
            kwargs["eo"] = "|".join(exclude_options)
        if include_options:
            where_clause += " AND options REGEXP :io"
            # include_options must be sorted since SQLite doesn't support arrays or the ALL operator
            # so we must use regex for requiring a set of options
            kwargs["io"] = r"[\d\D]+".join(sorted(include_options))

        res = self._conn.execute(
            "SELECT * FROM vehicles WHERE code_type=:ct" + where_clause, kwargs
        ).fetchall()

        if self._conn.in_transaction:
            self._conn.commit()

        return [
            {
                "vin": r[0],
                "code_type": r[1],
                "color": r[2],
                "upholstery": r[3],
                "production_date": r[4],
                "options": loads(r[5]),
            }
            for r in res
        ]

    def delete_vehicles(self, vin_list: t.List[str]) -> None:
        self._conn.execute(
            "DELETE FROM vehicles WHERE vin IN (:vl)", {"vl": ", ".join(vin_list)}
        )

        if self._conn.in_transaction:
            self._conn.commit()

    def get_option_mapping(self, code_type: str) -> t.Dict[str, str]:
        res = self._conn.execute(
            "SELECT id, name FROM options WHERE code_type=:ct", {"ct": code_type}
        ).fetchall()

        if self._conn.in_transaction:
            self._conn.commit()

        return {r[0]: r[1] for r in res}

    def get_all_code_types(self) -> t.List[str]:
        code_types = self._conn.execute(
            "SELECT DISTINCT code_type FROM vehicles"
        ).fetchall()
        if self._conn.in_transaction:
            self._conn.commit()
        return [c[0] for c in code_types]
