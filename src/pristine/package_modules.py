import importlib
import pkgutil


def import_package_modules(package_name: str) -> None:
    package = importlib.import_module(package_name)
    for module in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package_name}.{module.name}")
