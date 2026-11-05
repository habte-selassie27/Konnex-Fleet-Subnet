"""Simulation asset validation — Phase 1.

Verifies the warehouse world and AMR model assets are well-formed and carry
the elements the docs promise (15 shelves, 5 pickup + 5 delivery zones, 2
charging stations, diff-drive + LiDAR + IMU plugins). Pure XML checks — no
Gazebo needed, so they run in CI and on this machine.

NOTE: The XACRO file uses ${...} property syntax which is not valid XML.
We preprocess it with regex substitution before parsing with ElementTree.
"""

import re
from pathlib import Path
from xml.etree import ElementTree

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORLD_SDF = ROOT / "simulation" / "worlds" / "warehouse_v1.sdf"
ROBOT_XACRO = ROOT / "simulation" / "robots" / "amr_model.urdf.xacro"
BRIDGE_YAML = ROOT / "simulation" / "bridge" / "robot_bridge.yaml"

# Default values for xacro properties (from the XACRO file header)
_XACRO_DEFAULTS = {
    "chassis_length": "0.5",
    "chassis_width": "0.5",
    "chassis_height": "0.25",
    "chassis_mass": "20.0",
    "wheel_radius": "0.15",
    "wheel_width": "0.05",
    "wheel_mass": "1.0",
    "wheel_base": "0.4",
    "lidar_height": "0.25",
    "pi": "3.14159265358979",
}


def _preprocess_xacro(text: str) -> str:
    """Replace ${...} xacro property references with default values."""
    props = dict(_XACRO_DEFAULTS)

    # Extract property definitions from the file: <xacro:property name="..." value="..."/>
    for match in re.finditer(r'<xacro:property\s+name="(\w+)"\s+value="([^"]+)"', text):
        props[match.group(1)] = match.group(2)

    def _replace(m: re.Match[str]) -> str:
        expr = m.group(1).strip()
        # Handle simple property references
        if expr in props:
            return props[expr]
        # Handle arithmetic: e.g. wheel_base/2, -chassis_height/2 + wheel_radius
        try:
            # Evaluate with only the known properties as variables
            return str(eval(expr, {"__builtins__": {}}, props))  # noqa: S307
        except Exception:
            return "0"  # fallback for unresolvable expressions

    return re.sub(r"\$\{([^}]+)\}", _replace, text)


class TestWarehouseWorld:
    def test_sdf_is_well_formed_xml(self) -> None:
        ElementTree.parse(WORLD_SDF)  # raises ParseError on malformed XML

    def test_has_world_and_physics(self) -> None:
        root = ElementTree.parse(WORLD_SDF).getroot()
        assert root.tag == "sdf"
        assert root.find("world") is not None
        assert root.find("world/physics") is not None

    def test_has_fifteen_shelves(self) -> None:
        root = ElementTree.parse(WORLD_SDF).getroot()
        shelves = [m for m in root.findall("world/model") if m.get("name", "").startswith("shelf_")]
        assert len(shelves) == 15

    def test_has_five_pickup_and_five_delivery_zones(self) -> None:
        root = ElementTree.parse(WORLD_SDF).getroot()
        pickups = [
            m for m in root.findall("world/model") if m.get("name", "").startswith("pickup_zone_")
        ]
        deliveries = [
            m for m in root.findall("world/model") if m.get("name", "").startswith("delivery_zone_")
        ]
        assert len(pickups) == 5
        assert len(deliveries) == 5

    def test_has_two_charging_stations(self) -> None:
        root = ElementTree.parse(WORLD_SDF).getroot()
        stations = [
            m
            for m in root.findall("world/model")
            if m.get("name", "").startswith("charging_station_")
        ]
        assert len(stations) == 2

    def test_has_four_walls_and_floor(self) -> None:
        root = ElementTree.parse(WORLD_SDF).getroot()
        names = {m.get("name") for m in root.findall("world/model")}
        assert {"floor", "wall_north", "wall_south", "wall_east", "wall_west"} <= names


class TestAmrModel:
    def _parse_xacro(self) -> ElementTree.Element:
        """Parse the XACRO file after preprocessing ${...} expressions."""
        raw = ROBOT_XACRO.read_text(encoding="utf-8")
        xml_text = _preprocess_xacro(raw)
        return ElementTree.fromstring(xml_text)

    def test_xacro_is_well_formed_xml(self) -> None:
        self._parse_xacro()  # raises ParseError on malformed XML

    def test_has_diff_drive_plugin(self) -> None:
        root = self._parse_xacro()
        plugins = [p for p in root.findall(".//plugin") if "DiffDrive" in (p.get("name") or "")]
        assert len(plugins) == 1

    def test_has_lidar_and_imu_sensors(self) -> None:
        root = self._parse_xacro()
        sensors = [s for s in root.findall(".//sensor") if s.get("name") in ("lidar", "imu")]
        assert len(sensors) == 2

    def test_lidar_spec_matches_build_doc(self) -> None:
        root = self._parse_xacro()
        lidar = [s for s in root.findall(".//sensor") if s.get("name") == "lidar"][0]
        ranges = lidar.find(".//range")
        samples = lidar.find(".//horizontal/samples")
        max_range = ranges.find("max") if ranges is not None else None
        assert max_range is not None and max_range.text is not None
        assert float(max_range.text) == 10.0
        assert samples is not None and samples.text is not None
        assert int(samples.text) == 360

    def test_has_wheels_and_odometry_links(self) -> None:
        root = self._parse_xacro()
        links = {link.get("name") for link in root.findall("link")}
        assert {"base_link", "wheel_left", "wheel_right", "lidar_link"} <= links


class TestBridgeConfig:
    def test_bridge_yaml_is_valid_and_covers_five_robots(self) -> None:
        entries = yaml.safe_load(BRIDGE_YAML.read_text())
        assert isinstance(entries, list) and len(entries) >= 1
        ros_topics = {e["ros_topic_name"] for e in entries}
        for i in range(5):
            assert f"/robot_{i}/odom" in ros_topics
            assert f"/robot_{i}/cmd_vel" in ros_topics

    def test_bridge_entries_have_required_keys(self) -> None:
        entries = yaml.safe_load(BRIDGE_YAML.read_text())
        required = {"ros_topic_name", "gz_topic_name", "ros_type_name", "gz_type_name", "direction"}
        for entry in entries:
            assert required <= set(entry)
