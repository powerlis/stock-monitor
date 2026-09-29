"""Synchronize the current constituent list without erasing historical prices."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

path = Path(__file__).with_name("update-component-stocks.py")
spec = spec_from_file_location("component_updater", path)
module = module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == "__main__":
    module.sync_constituents(module.init_firestore())
