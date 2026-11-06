"""Compatibility alias: this module is ``cookieguard.browser_use.demo.app``."""

import importlib
import sys

sys.modules[__name__] = importlib.import_module('cookieguard.browser_use.demo.app')
