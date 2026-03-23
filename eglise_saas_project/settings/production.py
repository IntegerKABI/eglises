"""Production settings profile."""

import os

os.environ.setdefault("DEBUG", "False")

from .base import *  # noqa: F401,F403
from .base import _env_bool, _env_list

DEBUG = _env_bool("DEBUG", default=False)
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", default=[])
