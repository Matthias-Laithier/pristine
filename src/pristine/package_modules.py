import importlib
import pkgutil


def import_package_modules(package_name: str) -> None:
    package = importlib.import_module(package_name)
    for module in pkgutil.walk_packages(package.__path__, f"{package_name}."):
        importlib.import_module(module.name)
