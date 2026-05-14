# SPDX-License-Identifier: MIT

import importlib.util
import sys
from pathlib import Path


def load_upstream_module(module_name, current_file):
    current_path = Path(current_file).resolve()
    relative_path = Path(*module_name.split(".")).with_suffix(".py")
    for path_entry in sys.path:
        candidate = (Path(path_entry) / relative_path).resolve()
        if candidate == current_path or not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location(
            f"_ditdah32_upstream_{module_name.replace('.', '_')}",
            candidate,
        )
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise ImportError(f"Cannot find upstream module for {module_name}")
