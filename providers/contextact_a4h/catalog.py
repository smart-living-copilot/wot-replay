"""Sensor catalog for the ContextAct@A4H dataset.

The dataset's ``Variable Description.xlsx`` lists ~370 measured *variables*.
Many of those variables belong to the same physical device (a power meter
reports power/voltage/current/energy; an environment node reports
CO2/temperature/humidity; a water point reports total + instantaneous flow).

This module parses the spreadsheet (stdlib only — no openpyxl dependency) and
groups the variables into one "device" per physical unit, each carrying one
property per underlying variable. The result is ~159 devices.
"""

import re
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Variables that are activity / people / indoor-location annotations rather
# than sensor or weather measurements — excluded from this provider.
EXCLUDED_IDS = {"current_activity", "current_people", "current_position"}

# --- Human-readable translations (dataset labels are partly French) ---
APPLIANCE_EN = {
    "Chauffe_Eau": "Water Heater",
    "Eclairage": "Lighting",
    "Four": "Oven",
    "Frigo": "Fridge",
    "Hote": "Range Hood",
    "Lave_Linge": "Washing Machine",
    "Lave_Vaisselle": "Dishwasher",
    "Plaques": "Stove",
    "Volets_Roulants": "Roller Shutters",
}
WATER_TEMP_EN = {"Chaude": "Hot", "Froide": "Cold"}
WATER_POINT_EN = {
    "Douche": "Shower",
    "Evier": "Kitchen Sink",
    "Lavabo": "Washbasin",
    "General": "General",
    "WC": "Toilet",
}
ROOM_EN = {
    "Cuisine": "Kitchen",
    "cuisine": "Kitchen",
    "Salon": "Living Room",
    "salon": "Living Room",
    "Chambre": "Bedroom",
    "chambre": "Bedroom",
    "SDB": "Bathroom",
    "sdb": "Bathroom",
    "Bureau": "Study Room",
    "bureau": "Study Room",
    "Lit": "Bed",
    "Table": "Dining Table",
    "couloir": "Hallway",
    "couloirE": "Hallway (Entrance)",
}

# Sensor-type keywords that imply a numeric value when the spreadsheet leaves
# the "Variable Type" column blank.
_NUMERIC_TYPE_HINTS = (
    "meter", "temperature", "co2", "carbon dioxide", "humidity", "power",
    "energy", "tension", "voltage", "intensity", "noise", "brightness",
    "pressure", "dimmer", "dimming", "battery", "speed", "factor",
)


class Variable:
    """One measured variable (a row in Variable Description.xlsx)."""

    __slots__ = ("sid", "sensor_type", "measured", "var_type", "unit", "location")

    def __init__(self, sid, sensor_type, measured, var_type, unit, location):
        self.sid = sid
        self.sensor_type = sensor_type
        self.measured = measured
        self.var_type = var_type
        self.unit = unit
        self.location = location

    @property
    def json_type(self) -> str:
        vt = self.var_type.lower()
        if any(k in vt for k in ("number", "double", "float", "int")):
            return "number"
        if vt:  # explicitly Binary / String / Vector
            return "string"
        st = self.sensor_type.lower()
        return "number" if any(k in st for k in _NUMERIC_TYPE_HINTS) else "string"


def _column_letter(ref: str) -> str:
    return re.match(r"[A-Z]+", ref).group()


def load_variables(xlsx_path: Path) -> list[Variable]:
    """Parse Variable Description.xlsx into Variable records (stdlib only)."""
    with zipfile.ZipFile(xlsx_path) as z:
        shared: list[str] = []
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.iter(_NS + "si"):
            shared.append("".join(t.text or "" for t in si.iter(_NS + "t")))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    rows: list[list[str]] = []
    for row in sheet.iter(_NS + "row"):
        cells: dict[str, str] = {}
        for c in row.findall(_NS + "c"):
            v = c.find(_NS + "v")
            if v is None or v.text is None:
                continue
            cells[_column_letter(c.get("r"))] = (
                shared[int(v.text)] if c.get("t") == "s" else v.text
            )
        rows.append([cells.get(L, "").strip() for L in "ABCDEF"])

    variables = []
    for r in rows[1:]:  # skip header
        if not r[0]:
            continue
        variables.append(Variable(r[0], r[1], r[2], r[3], r[4], r[5]))
    return variables


def device_key(sid: str) -> str | None:
    """Map a sensor id to its physical-device key, or None to exclude it."""
    if sid in EXCLUDED_IDS:
        return None
    m = re.match(r"(Puissance|Tension|Intensite|Energie_Partielle|Energie_Totale)_(.+)$", sid)
    if m:
        return f"meter:{m.group(2)}"
    m = re.match(r"(Eau_(?:Chaude|Froide)_.+)_(Total|Instantanee)$", sid)
    if m:
        return f"water:{m.group(1)}"
    m = re.match(r"R(\d+)_", sid)
    if m:
        return f"radiator:{m.group(1)}"
    m = re.match(r"(?:CO2|Humidite|Temperature|Leds_CO2)_(Cuisine|Salon|Chambre|SDB)$", sid)
    if m:
        return f"env:{m.group(1)}"
    m = re.match(r"(?:Presence|Luminosite)_(\w+)$", sid)
    if m:
        return f"motionlux:{m.group(1)}"
    m = re.match(r"Noise_(\w+)$", sid)
    if m:
        return f"noise:{m.group(1)}"
    m = re.match(r"(?:Color|Dimm|Toggle)_(\d+)$", sid)
    if m:
        return f"hue:{m.group(1)}"
    m = re.match(r"music_(bureau|chambre|cuisine|salon|sdb)", sid, re.I)
    if m:
        return f"music:{m.group(1).lower()}"
    m = re.match(r"I(\d+)(?:_|$)", sid)
    if m:
        return f"switch:{m.group(1)}"
    if sid.startswith("Telecommande18"):
        return "remote:18"
    if sid == "Telecommande6":
        return "remote:6"
    if sid.startswith("Domicube_"):
        return "domicube"
    if sid.startswith("Thermostat_"):
        return "thermostat"
    if sid.startswith("tv_salon"):
        return "tv_salon"
    if sid in {"P_active", "PF", "V1N", "Freq_totale", "E_active", "Status_TGBT"}:
        return "main_meter"
    if sid.startswith("record_"):
        return "scene_recorder"
    return f"single:{sid}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _device_meta(key: str, members: list[Variable]) -> tuple[str, str, str]:
    """Return (title, category, location) for a device group."""
    cat, _, arg = key.partition(":")
    # Most common non-empty location among members.
    locs = [m.location for m in members if m.location]
    location = max(set(locs), key=locs.count) if locs else ""

    if cat == "meter":
        return f"{APPLIANCE_EN.get(arg, arg)} Energy Meter", cat, location
    if cat == "water":
        parts = arg.split("_")  # Eau_Chaude_Douche -> [Eau, Chaude, Douche]
        temp = WATER_TEMP_EN.get(parts[1], parts[1]) if len(parts) > 1 else ""
        point = WATER_POINT_EN.get(parts[-1], parts[-1])
        return f"{temp} Water — {point}".strip(), cat, location
    if cat == "radiator":
        return f"Radiator {arg}", cat, location
    if cat == "env":
        return f"Environment — {ROOM_EN.get(arg, arg)}", cat, location
    if cat == "motionlux":
        return f"Motion & Light — {ROOM_EN.get(arg, arg)}", cat, location
    if cat == "noise":
        return f"Noise — {ROOM_EN.get(arg, arg)}", cat, location
    if cat == "hue":
        return f"Hue Bulb {arg}", cat, location
    if cat == "music":
        return f"Music Player — {ROOM_EN.get(arg, arg)}", cat, location
    if cat == "switch":
        return f"Wall Switch {arg}", cat, location
    if cat == "remote":
        return f"Remote Control {arg}", cat, location
    if cat == "domicube":
        return "Domicube", cat, location
    if cat == "thermostat":
        return "Thermostat", cat, location
    if cat == "tv_salon":
        return "Living Room TV", cat, location
    if cat == "main_meter":
        return "Main Electricity Meter", cat, location
    if cat == "scene_recorder":
        return "Scene Recorder", cat, location
    # single:<sid> — name after the variable's measured property.
    var = members[0]
    return (var.measured or var.sid), "single", location


def _property_entry(var: Variable) -> dict:
    return {
        "sensor_id": var.sid,
        "description": var.measured or var.sid,
        "unit": var.unit,
        "json_type": var.json_type,
        "sensor_type": var.sensor_type,
    }


def build_devices(variables: list[Variable], present_ids: set[str] | None = None) -> list[dict]:
    """Group variables into physical-device definitions.

    If *present_ids* is given, only variables whose id appears in the data are
    included (and devices left with no properties are dropped).
    """
    groups: dict[str, list[Variable]] = defaultdict(list)
    for var in variables:
        if present_ids is not None and var.sid not in present_ids:
            continue
        key = device_key(var.sid)
        if key is None:
            continue
        groups[key].append(var)

    devices = []
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda v: v.sid)
        title, category, location = _device_meta(key, members)
        cat, _, arg = key.partition(":")
        device_id = f"a4h-{_slug(cat)}" + (f"-{_slug(arg)}" if arg else "")
        props = [_property_entry(v) for v in members]
        devices.append(
            {
                "id": device_id,
                "type": "a4h_device",
                "title": title,
                "description": (
                    f"{title} in the Amiqual4Home apartment (ContextAct@A4H dataset)"
                ),
                "location": {"room": location} if location else {},
                "metadata": {
                    "dataset": "ContextAct@A4H",
                    "category": category,
                    "device_key": key,
                    "room": location,
                },
                "properties": props,
            }
        )
    return devices


def sensor_to_device(devices: list[dict]) -> dict[str, str]:
    """Map each underlying sensor id to its owning device id."""
    index = {}
    for d in devices:
        for p in d["properties"]:
            index[p["sensor_id"]] = d["id"]
    return index
