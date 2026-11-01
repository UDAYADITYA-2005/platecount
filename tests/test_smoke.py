import importlib
import pkgutil

import bench
import platecount


def test_every_module_imports() -> None:
    names = [
        info.name
        for pkg in (platecount, bench)
        for info in pkgutil.walk_packages(pkg.__path__, f"{pkg.__name__}.")
    ]
    assert "platecount.meta.client" in names
    assert "bench.run" in names
    for name in names:
        importlib.import_module(name)
