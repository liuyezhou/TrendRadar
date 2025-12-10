# config/__init__.py
from .loader import *
from .constants import SMTP_CONFIGS
CONFIG = load_config()