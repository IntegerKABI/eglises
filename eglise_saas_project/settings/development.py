"""Development settings profile."""

import os

os.environ.setdefault("DEBUG", "True")

from .base import *  # noqa: F401,F403
from .base import _env_bool, _env_list

DEBUG = _env_bool("DEBUG", default=True)
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
