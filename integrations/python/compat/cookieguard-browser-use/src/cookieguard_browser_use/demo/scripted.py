"""Compatibility alias: this module is ``cookieguard.browser_use.demo.scripted``."""

import importlib
import sys

sys.modules[__name__] = importlib.import_module('cookieguard.browser_use.demo.scripted')
