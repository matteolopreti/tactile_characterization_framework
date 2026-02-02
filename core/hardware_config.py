import importlib
import json
import os
import inspect

from drivers.auto_detect import auto_detect_components, auto_detect_classes, list_driver_classes


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "hardware.json")

DEFAULT_CONFIG = {
    "mode": "sim",
    "stage": {
        "driver": "drivers.acs_stage.ACSMotionStage",
        "config": {
            "ip": "10.0.0.100",
            "port": 701
        }
    },
    "load_cell": {
        "driver": "drivers.ati_daq.NIDAQLoadCell",
        "config": {
            "channel_base": "Dev1/ai",
            "cal_file": "FT58072.cal"
        }
    },
    "sensor": {
        "driver": "drivers.serial_sensor.SerialMagneticSensor",
        "config": {
            "port": "COM4",
            "baud": 115200
        }
    }
}


def _copy_default_config():
    return json.loads(json.dumps(DEFAULT_CONFIG))


def _merge_defaults(cfg, defaults):
    if not isinstance(cfg, dict):
        return json.loads(json.dumps(defaults))
    for key, val in defaults.items():
        if key not in cfg:
            cfg[key] = json.loads(json.dumps(val))
        elif isinstance(val, dict):
            cfg[key] = _merge_defaults(cfg.get(key), val)
    return cfg


def _normalize_driver_path(path):
    if not isinstance(path, str):
        return path
    if path.startswith("Drivers."):
        return "drivers." + path[len("Drivers."):]
    if path.startswith("Interfaces."):
        return "interfaces." + path[len("Interfaces."):]
    if path.startswith("Core."):
        return "core." + path[len("Core."):]
    if path.startswith("GUI."):
        return "gui." + path[len("GUI."):]
    return path


def _normalize_config_paths(cfg):
    for key in ("stage", "load_cell", "sensor"):
        info = cfg.get(key, {})
        driver = info.get("driver")
        if driver:
            info["driver"] = _normalize_driver_path(driver)
            cfg[key] = info
    return cfg


def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        cfg = _copy_default_config()
        save_config(cfg, path)
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg = _merge_defaults(cfg, _copy_default_config())
    return _normalize_config_paths(cfg)


def save_config(cfg, path=CONFIG_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _class_path(cls):
    return f"{cls.__module__}.{cls.__name__}"


def list_driver_options(base_cls):
    drivers = list_driver_classes(base_cls)
    options = []
    for cls in drivers:
        options.append({
            "name": cls.__name__,
            "path": _class_path(cls),
            "class": cls
        })
    options.sort(key=lambda x: x["name"].lower())
    return options


def list_serial_ports():
    try:
        from serial.tools import list_ports
    except Exception:
        return []
    return [p.device for p in list_ports.comports()]


def suggest_serial_port(driver_cls, config=None):
    try:
        from serial.tools import list_ports
    except Exception:
        return None

    ports = [p.device for p in list_ports.comports()]
    if not ports:
        return None

    probe = getattr(driver_cls, "probe_port", None)
    if callable(probe):
        config = config or {}
        for port in ports:
            try:
                if probe(port, config=config):
                    return port
            except Exception:
                continue

    if len(ports) == 1:
        return ports[0]
    return None


def resolve_class(path):
    if not path:
        return None
    module_name, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def _init_driver(cls, config):
    if cls is None:
        raise RuntimeError("Driver class not found.")
    if not config:
        return cls()
    sig = inspect.signature(cls.__init__)
    kwargs = {}
    for name in sig.parameters:
        if name == "self":
            continue
        if name in config:
            kwargs[name] = config[name]
    return cls(**kwargs)


def auto_detect_driver_classes(cfg=None):
    if cfg is None:
        cfg = load_config()
    else:
        cfg = _normalize_config_paths(cfg)
    return auto_detect_classes(
        stage_config=cfg.get("stage", {}).get("config"),
        load_cell_config=cfg.get("load_cell", {}).get("config"),
        sensor_config=cfg.get("sensor", {}).get("config")
    )


def get_hardware_components(cfg=None):
    if cfg is None:
        cfg = load_config()
    else:
        cfg = _normalize_config_paths(cfg)

    mode = (cfg.get("mode") or "manual").strip().lower()

    if mode == "sim":
        print("[Config] HARDWARE_MODE is 'sim'. Loading Mock drivers...")
        from drivers.mock_drivers import MockMotionStage, MockLoadCell, MockTactileSensor
        return MockMotionStage(), MockLoadCell(), MockTactileSensor()

    if mode == "auto":
        print("[Config] AUTO mode enabled. Scanning for drivers...")
        return auto_detect_components(
            stage_config=cfg.get("stage", {}).get("config"),
            load_cell_config=cfg.get("load_cell", {}).get("config"),
            sensor_config=cfg.get("sensor", {}).get("config")
        )

    if mode != "manual":
        raise ValueError(f"Unknown hardware mode: {mode}")

    stage_info = cfg.get("stage", {})
    load_cell_info = cfg.get("load_cell", {})
    sensor_info = cfg.get("sensor", {})

    stage_cls = resolve_class(stage_info.get("driver"))
    load_cell_cls = resolve_class(load_cell_info.get("driver"))
    sensor_cls = resolve_class(sensor_info.get("driver"))

    stage = _init_driver(stage_cls, stage_info.get("config") or {})
    load_cell = _init_driver(load_cell_cls, load_cell_info.get("config") or {})
    sensor = _init_driver(sensor_cls, sensor_info.get("config") or {})
    return stage, load_cell, sensor
