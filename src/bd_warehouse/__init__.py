"""bd_warehouse: a build123d parametric part collection"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("bd_warehouse")
except PackageNotFoundError:
    __version__ = "unknown version"
