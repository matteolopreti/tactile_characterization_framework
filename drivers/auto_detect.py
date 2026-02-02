import importlib
import inspect
import os
import pkgutil

from interfaces.motion_stage import IMotionStage
from interfaces.load_cell import ILoadCell
from interfaces.tactile_sensor import ITactileSensor


def _iter_driver_modules():
    pkg_dir = os.path.dirname(__file__)
    for info in pkgutil.iter_modules([pkg_dir]):
        name = info.name
        if name.startswith("_") or name == "auto_detect":
            continue
        yield importlib.import_module(f"{__package__}.{name}")


def _iter_driver_classes(base_cls):
    for module in _iter_driver_modules():
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is base_cls:
                continue
            if issubclass(obj, base_cls):
                yield obj


def list_driver_classes(base_cls):
    return list(_iter_driver_classes(base_cls))


def _probe_driver(cls, config):
    probe = getattr(cls, "probe", None)
    if not callable(probe):
        return False
    try:
        return bool(probe(config or {}))
    except Exception:
        return False


def _init_driver(cls, config):
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


def _select_driver(base_cls, config):
    best_cls = None
    best_priority = None
    for cls in _iter_driver_classes(base_cls):
        if not _probe_driver(cls, config):
            continue
        priority = getattr(cls, "PROBE_PRIORITY", 0)
        if best_cls is None or priority > best_priority:
            best_cls = cls
            best_priority = priority
    if best_cls is None:
        raise RuntimeError(f"No compatible driver found for {base_cls.__name__}")
    return best_cls


def auto_detect_components(stage_config=None, load_cell_config=None, sensor_config=None):
    stage_cls = _select_driver(IMotionStage, stage_config)
    load_cell_cls = _select_driver(ILoadCell, load_cell_config)
    sensor_cls = _select_driver(ITactileSensor, sensor_config)

    print(f"[AutoDetect] Stage: {stage_cls.__name__}")
    print(f"[AutoDetect] LoadCell: {load_cell_cls.__name__}")
    print(f"[AutoDetect] Sensor: {sensor_cls.__name__}")

    stage = _init_driver(stage_cls, stage_config)
    load_cell = _init_driver(load_cell_cls, load_cell_config)
    sensor = _init_driver(sensor_cls, sensor_config)
    return stage, load_cell, sensor


def auto_detect_classes(stage_config=None, load_cell_config=None, sensor_config=None):
    stage_cls = _select_driver(IMotionStage, stage_config)
    load_cell_cls = _select_driver(ILoadCell, load_cell_config)
    sensor_cls = _select_driver(ITactileSensor, sensor_config)
    return stage_cls, load_cell_cls, sensor_cls
