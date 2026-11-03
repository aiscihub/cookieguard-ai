"""Refuse to build a wheel without a complete, verified vendored engine."""

import hashlib
import json
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
	def initialize(self, version, build_data):
		engine = Path(self.root) / 'src' / 'cookieguard_browser_use' / '_node'
		manifest_path = engine / 'manifest.json'
		if not manifest_path.is_file():
			raise RuntimeError('Vendored engine missing. Run: node scripts/vendor_engine.mjs --registry')
		manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
		expected = dict(manifest['bridge'])
		for package in manifest['packages']:
			expected.update(package['files'])
		for relative, digest in expected.items():
			if hashlib.sha256((engine / relative).read_bytes()).hexdigest() != digest:
				raise RuntimeError('Vendored engine does not match its manifest. Re-run scripts/vendor_engine.mjs.')
