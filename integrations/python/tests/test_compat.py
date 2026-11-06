"""The cookieguard-browser-use compatibility package exposes the same objects as cookieguard."""

import subprocess
import sys

import pytest

compat = pytest.importorskip('cookieguard_browser_use')

import cookieguard  # noqa: E402
import cookieguard.browser_use as browser_use  # noqa: E402


def test_compat_names_are_the_umbrella_objects():
	for name in ('CookieGuardAudit', 'AuditResult', 'Finding', 'CookieGuardError', 'CookiePolicyError',
			'ACTION_DESCRIPTION', 'DEFAULT_ACTION_NAME'):
		assert getattr(compat, name) is getattr(browser_use, name) is getattr(cookieguard, name)
	assert compat.__version__ == cookieguard.__version__


def test_compat_demo_modules_are_aliases():
	from cookieguard_browser_use.demo import app, scripted

	from cookieguard.browser_use.demo import app as new_app, scripted as new_scripted
	assert app is new_app and scripted is new_scripted


def test_legacy_demo_entry_point_still_runs():
	completed = subprocess.run([sys.executable, '-m', 'cookieguard_browser_use.demo', '--help'],
		capture_output=True, text=True, timeout=60)
	assert completed.returncode == 0 and 'usage' in completed.stdout.lower()
