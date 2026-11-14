"""Verify install and upgrade paths from the published packages to the local wheels.

    python scripts/verify_upgrade.py DIST_DIR [--python /path/to/python3.11+]

DIST_DIR must contain the cookieguard and cookieguard-browser-use wheels at the version in
pyproject.toml. Earlier releases come from PyPI. Each scenario uses a fresh virtualenv outside the repository and
checks that `pip check` passes, that `cookieguard_browser_use` and `cookieguard` expose the
same objects, that no 0.1 implementation files survive under `cookieguard_browser_use/`,
and that the vendored engine verifies.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

VERSION = tomllib.loads((Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text())['project']['version']

PROBE = r'''
import importlib.metadata as m, pathlib, cookieguard, cookieguard.browser_use as bu, cookieguard_browser_use as compat
from cookieguard._engine import verify_engine_files
verify_engine_files()
assert compat.CookieGuardAudit is bu.CookieGuardAudit is cookieguard.CookieGuardAudit
assert compat.flush_usage_metrics is bu.flush_usage_metrics is cookieguard.flush_usage_metrics
from cookieguard_browser_use.demo import app, scripted
from cookieguard.browser_use.demo import app as new_app, scripted as new_scripted
assert app is new_app and scripted is new_scripted
leftovers = sorted(p.name for p in pathlib.Path(compat.__file__).parent.iterdir() if p.name.startswith('_') and p.name not in ('__init__.py', '__pycache__'))
assert not leftovers, leftovers
print(m.version('cookieguard'), m.version('cookieguard-browser-use'))
'''

SCENARIOS = {
	f'fresh install of cookieguard-browser-use {VERSION}': [[f'cookieguard-browser-use=={VERSION}']],
	'upgrade from cookieguard and cookieguard-browser-use 0.3.0': [['cookieguard==0.3.0', 'cookieguard-browser-use==0.3.0'],
		['-U', f'cookieguard=={VERSION}', f'cookieguard-browser-use=={VERSION}']],
	'upgrade from cookieguard and cookieguard-browser-use 0.2.0': [['cookieguard==0.2.0', 'cookieguard-browser-use==0.2.0'],
		['-U', f'cookieguard=={VERSION}', f'cookieguard-browser-use=={VERSION}']],
	'upgrade from cookieguard-browser-use 0.1.0': [['cookieguard-browser-use==0.1.0'], ['-U', f'cookieguard-browser-use=={VERSION}']],
	'upgrade from cookieguard 0.1.0': [['cookieguard==0.1.0'], ['-U', f'cookieguard=={VERSION}'], ['-U', f'cookieguard-browser-use=={VERSION}']],
}


def run(python: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
	env = {key: value for key, value in os.environ.items() if not key.startswith(('PYTHON', 'VIRTUAL_ENV'))}
	env.update(PIP_DISABLE_PIP_VERSION_CHECK='1', ANONYMIZED_TELEMETRY='false', BROWSER_USE_CLOUD_SYNC='false',
		COOKIEGUARD_USAGE_METRICS='0', DO_NOT_TRACK='1')
	return subprocess.run([str(python), *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=900)


def require(completed: subprocess.CompletedProcess, step: str) -> str:
	if completed.returncode != 0:
		sys.stdout.write(completed.stdout[-3000:])
		sys.stderr.write(completed.stderr[-3000:])
		raise SystemExit(f'{step} failed (exit {completed.returncode}).')
	return completed.stdout


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument('dist', type=Path)
	parser.add_argument('--python', default=getattr(sys, '_base_executable', sys.executable))
	args = parser.parse_args()
	dist = args.dist.resolve()
	for name, steps in SCENARIOS.items():
		with tempfile.TemporaryDirectory(prefix='cookieguard-upgrade-') as temporary:
			home = Path(temporary).resolve()
			require(subprocess.run([args.python, '-m', 'venv', str(home / 'venv')], capture_output=True, text=True), 'venv')
			python = home / 'venv' / 'bin' / 'python'
			for step in steps:
				require(run(python, '-m', 'pip', 'install', '-q', '--find-links', str(dist), *step, cwd=home), f'{name}: pip install {" ".join(step)}')
			require(run(python, '-m', 'pip', 'check', cwd=home), f'{name}: pip check')
			versions = require(run(python, '-I', '-c', PROBE, cwd=home), f'{name}: import probe').split()
			help_text = require(run(python, '-m', 'cookieguard_browser_use.demo', '--help', cwd=home), f'{name}: legacy demo entry point')
			if 'usage' not in help_text.lower():
				raise SystemExit(f'{name}: legacy demo entry point printed no usage.')
			print(f'ok  {name}: cookieguard {versions[0]}, cookieguard-browser-use {versions[1]}; same objects, '
				'no stale 0.1 files, engine verified, pip check clean, legacy entry point works')
	return 0


if __name__ == '__main__':
	sys.exit(main())
