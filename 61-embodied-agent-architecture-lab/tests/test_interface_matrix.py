"""Validate every declared interface, schema, and QoS contract field."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from embodied.contracts import FRAME_IDS, ResultCode


ROOT = Path(__file__).resolve().parents[1]
KNOWN_UNITS = {"m", "m2", "s", "m/s", "rad/s"}


class InterfaceMatrixTests(unittest.TestCase):
    def test_catalog_has_160_independent_contract_cases(self) -> None:
        catalog = json.loads(
            (ROOT / "contracts/interface-catalog.v1.json").read_text(encoding="utf-8")
        )
        interfaces = catalog["interfaces"]
        self.assertEqual(len(interfaces), 12)
        global_checks = (
            (
                "schema",
                catalog.get("schema_version") == "embodied.interface-catalog.v1",
            ),
            ("clock", catalog.get("clock_domain") == "sim"),
            ("unique_names", len({entry["name"] for entry in interfaces}) == 12),
            (
                "unique_endpoints",
                len({entry.get("topic", entry.get("action")) for entry in interfaces})
                == 12,
            ),
        )
        for name, valid in global_checks:
            with self.subTest(interface="catalog", contract=name):
                self.assertTrue(valid)

        for entry in interfaces:
            name = entry["name"]
            endpoint = entry.get("topic", entry.get("action", ""))
            qos = entry["qos"]
            schema_file = (
                ROOT
                / "astra_interfaces"
                / ("action" if "action" in entry else "msg")
                / f"{name}.{'action' if 'action' in entry else 'msg'}"
            )
            checks = (
                ("name", bool(name) and name[0].isupper()),
                ("owner", entry["owner"].startswith("embodied_")),
                ("endpoint_kind", ("topic" in entry) != ("action" in entry)),
                ("endpoint_path", endpoint.startswith("/astra/")),
                (
                    "frame",
                    entry["frame"] in FRAME_IDS
                    and (
                        name not in {"Percept", "EntityState"}
                        or (
                            entry.get("allowed_frames")
                            == ["camera_optical_frame", "astra/base_footprint/lidar_2d"]
                            and (
                                name != "Percept"
                                or entry.get("internal_source_topics")
                                == [
                                    "/astra/perception/camera",
                                    "/astra/perception/lidar",
                                ]
                            )
                            and (
                                name != "EntityState"
                                or entry.get("internal_target_topic")
                                == "/astra/world/object_target"
                            )
                        )
                    ),
                ),
                (
                    "units",
                    bool(entry["units"])
                    and set(entry["units"].split(", ")) <= KNOWN_UNITS,
                ),
                (
                    "freshness",
                    type(entry["freshness_ms"]) is int
                    and 0 < entry["freshness_ms"] <= 5000,
                ),
                (
                    "deadline",
                    type(entry["deadline_ms"]) is int
                    and entry["freshness_ms"] <= entry["deadline_ms"] <= 5000,
                ),
                ("qos_depth", type(qos["depth"]) is int and 1 <= qos["depth"] <= 16),
                (
                    "qos_reliability",
                    qos["reliability"] in {"reliable", "best_effort"}
                    and (name != "Percept" or qos["reliability"] == "reliable"),
                ),
                (
                    "qos_durability",
                    qos["durability"] in {"volatile", "transient_local"},
                ),
                (
                    "result_codes",
                    bool(entry["result_codes"])
                    and len(entry["result_codes"]) == len(set(entry["result_codes"]))
                    and set(entry["result_codes"]) <= set(ResultCode.__members__),
                ),
                (
                    "ros_schema",
                    schema_file.is_file()
                    and "schema_version" in schema_file.read_text(encoding="utf-8"),
                ),
            )
            self.assertEqual(len(checks), 13)
            for field, valid in checks:
                with self.subTest(interface=name, contract=field):
                    self.assertTrue(valid)


if __name__ == "__main__":
    unittest.main()
