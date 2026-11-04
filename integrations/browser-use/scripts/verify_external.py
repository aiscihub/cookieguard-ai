"""Build the distribution and verify it as an external consumer would.

    python scripts/verify_external.py [--python /path/to/python3.11+]

1. Builds the wheel and sdist (the build hook re-verifies the vendored engine).
2. Checks wheel contents: engine, manifest, licenses; no tests or virtualenvs.
3. Creates a fresh virtualenv in a temporary directory outside the repository,
   installs the wheel with its declared dependencies, and confirms the package
   imports from that virtualenv rather than from the source tree.
4. Copies the test suite there and runs it, then runs the demo module.
   Then installs the sdist into a second clean venv (pip builds it from source),
   checks the engine hashes, and runs the demo again.
5. Writes sanitized evidence to artifacts/browser-use/ and checks that no
   synthetic canary appears in any output or saved file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent
CANARY_PREFIX = 'CGBU_CANARY_'


def sh(*args: str, cwd: Path, env: dict[str, str] | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
	completed = subprocess.run(list(args), cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
	if CANARY_PREFIX in completed.stdout + completed.stderr:
		raise SystemExit('Synthetic secret detected in command output; output withheld.')
	return completed


def require(completed: subprocess.CompletedProcess, step: str) -> None:
	if completed.returncode != 0:
		sys.stdout.write(completed.stdout[-4000:])
		sys.stderr.write(completed.stderr[-4000:])
		raise SystemExit(f'{step} failed (exit {completed.returncode}).')


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument('--python', default=getattr(sys, '_base_executable', sys.executable))
	args = parser.parse_args()
	evidence_dir = REPO / 'artifacts' / 'browser-use'
	evidence_dir.mkdir(parents=True, exist_ok=True)
	dist = HERE / 'dist'
	shutil.rmtree(dist, ignore_errors=True)
	require(sh(sys.executable, '-m', 'build', '--outdir', str(dist), cwd=HERE), 'build')
	wheel = next(dist.glob('*.whl'))
	sdist = next(dist.glob('*.tar.gz'))
	names = zipfile.ZipFile(wheel).namelist()
	required = ['cookieguard_browser_use/_node/bridge.mjs', 'cookieguard_browser_use/_node/manifest.json',
		'cookieguard_browser_use/_node/node_modules/@aiscihub/cookieguard-core/src/policy.js',
		'cookieguard_browser_use/_node/node_modules/@aiscihub/cookieguard-core/vendor/engine.cjs',
		'cookieguard_browser_use/_node/node_modules/@aiscihub/cookieguard-core/LICENSE',
		'cookieguard_browser_use/_node/node_modules/@aiscihub/cookieguard-playwright/src/index.js',
		'cookieguard_browser_use/py.typed', 'cookieguard_browser_use/demo/app.py']
	missing = [name for name in required if name not in names]
	if missing or not any(name.endswith('licenses/LICENSE') for name in names):
		raise SystemExit(f'Wheel is missing required files: {missing}')
	if any('/tests/' in name or '.venv' in name or name.endswith('.pyc') for name in names):
		raise SystemExit('Wheel contains files that should not be distributed.')
	print(f'Built {wheel.name} ({len(names)} files) and {sdist.name}; engine, manifest, and licenses present.')

	with tempfile.TemporaryDirectory(prefix='cookieguard-browser-use-consumer-') as temporary:
		consumer = Path(temporary).resolve()
		if REPO in consumer.parents:
			raise SystemExit('Consumer directory must be outside the repository.')
		venv = consumer / 'venv'
		require(sh(args.python, '-m', 'venv', str(venv), cwd=consumer), 'venv')
		python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
		env = {key: value for key, value in os.environ.items() if not key.startswith(('PYTHON', 'VIRTUAL_ENV'))}
		env.update(ANONYMIZED_TELEMETRY='false', BROWSER_USE_CLOUD_SYNC='false')
		require(sh(str(python), '-m', 'pip', 'install', '-q', f'{wheel}[test]', cwd=consumer, env=env), 'install')
		location = sh(str(python), '-c', 'import cookieguard_browser_use as c, browser_use, sys; '
			'print(c.__file__); print(c.__version__); print(sys.version.split()[0]); '
			'import importlib.metadata as m; print(m.version("browser-use")); print(m.version("cdp-use"))', cwd=consumer, env=env)
		require(location, 'import')
		module_path, version, python_version, browser_use_version, cdp_use_version = location.stdout.split()
		if not Path(module_path).resolve().is_relative_to(venv):
			raise SystemExit('Package imported from outside the consumer virtualenv.')
		print(f'Installed {version} into a clean Python {python_version} venv outside the repository '
			f'(browser-use {browser_use_version}, cdp-use {cdp_use_version}).')
		shutil.copytree(HERE / 'tests', consumer / 'tests')
		tests = sh(str(python), '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'tests', cwd=consumer, env=env, timeout=1200)
		require(tests, 'consumer tests')
		summary = tests.stdout.strip().splitlines()[-1]
		print(f'Consumer test suite: {summary}')
		demo = sh(str(python), '-m', 'cookieguard_browser_use.demo', cwd=consumer, env=env, timeout=600)
		require(demo, 'demo')
		(evidence_dir / 'demo-output.txt').write_text(demo.stdout)
		statuses = [line for line in demo.stdout.splitlines() if line.startswith('CookieGuard for Browser Use:')]
		print('Demo from the installed package:\n  ' + '\n  '.join(statuses))
		# Everything the run produced, excluding the installed environment and the copied
		# test sources (which define the canary prefix itself).
		produced = [path for path in consumer.rglob('*') if path.is_file()
			and path.relative_to(consumer).parts[0] not in ('venv', 'tests')]
		leaks = [str(path.relative_to(consumer)) for path in produced if CANARY_PREFIX.encode() in path.read_bytes()]
		if leaks:
			raise SystemExit(f'Synthetic secret found in consumer artifacts {leaks}; contents withheld.')
		print(f'Leak scan: {len(produced)} produced files checked outside venv/ and tests/.')

	# The sdist path: pip builds a wheel from the source archive, as it does for
	# users who install without wheels. Check the result imports, carries an intact
	# engine, and passes the end-to-end demo (real Chromium, synthetic session tokens).
	with tempfile.TemporaryDirectory(prefix='cookieguard-browser-use-sdist-') as temporary:
		consumer = Path(temporary).resolve()
		venv = consumer / 'venv'
		require(sh(args.python, '-m', 'venv', str(venv), cwd=consumer), 'sdist venv')
		python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
		env = {key: value for key, value in os.environ.items() if not key.startswith(('PYTHON', 'VIRTUAL_ENV'))}
		env.update(ANONYMIZED_TELEMETRY='false', BROWSER_USE_CLOUD_SYNC='false')
		require(sh(str(python), '-m', 'pip', 'install', '-q', '--no-binary', 'cookieguard-browser-use', str(sdist),
			cwd=consumer, env=env), 'sdist install')
		check = sh(str(python), '-c', 'import cookieguard_browser_use as c; from cookieguard_browser_use._engine import '
			'verify_engine_files; verify_engine_files(); print(c.__file__); print(c.__version__)', cwd=consumer, env=env)
		require(check, 'sdist import and engine check')
		sdist_path, sdist_version = check.stdout.split()
		if not Path(sdist_path).resolve().is_relative_to(venv) or sdist_version != version:
			raise SystemExit('sdist install imported the wrong package or version.')
		sdist_demo = sh(str(python), '-m', 'cookieguard_browser_use.demo', cwd=consumer, env=env, timeout=600)
		require(sdist_demo, 'sdist demo')
		sdist_statuses = [line for line in sdist_demo.stdout.splitlines() if line.startswith('CookieGuard for Browser Use:')]
		print(f'Installed {sdist_version} from {sdist.name} (built from source); engine hashes verified. Demo:\n  '
			+ '\n  '.join(sdist_statuses))
	evidence = {
		'wheel': wheel.name, 'wheelSha256': hashlib.sha256(wheel.read_bytes()).hexdigest(), 'sdist': sdist.name,
		'sdistSha256': hashlib.sha256(sdist.read_bytes()).hexdigest(),
		'consumerPython': python_version, 'browserUse': browser_use_version, 'cdpUse': cdp_use_version,
		'consumerTests': summary, 'demo': statuses, 'sdistDemo': sdist_statuses, 'canaryLeaks': 0,
	}
	(evidence_dir / 'external-install.json').write_text(json.dumps(evidence, indent=2) + '\n')
	print(f'Evidence written to {evidence_dir.relative_to(REPO)}/.')
	return 0


if __name__ == '__main__':
	sys.exit(main())
