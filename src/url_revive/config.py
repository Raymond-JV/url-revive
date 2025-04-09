from dynaconf import Dynaconf
from importlib.resources import files

settings_path = files("config").joinpath("settings.toml")
settings = Dynaconf(
    settings_files=[settings_path],
)
