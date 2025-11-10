from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("bd_warehouse")
except PackageNotFoundError:
    __version__ = "unknown version"
