"""Check the built PyPI descriptions and release tag without running the test suite."""

from __future__ import annotations

import os
import re
import tarfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def verify(description: str, filename: str, version: str) -> None:
	metadata = Parser().parsestr(description)
	if metadata['Name'] != 'cookieguard' or metadata['Version'] != version:
		raise SystemExit(f'{filename}: package name or version does not match pyproject.toml.')
	if metadata['Description-Content-Type'] != 'text/markdown':
		raise SystemExit(f'{filename}: description is not Markdown.')
	readme = metadata.get_payload()
	links = re.findall(r'\]\(([^)\s]+)\)', readme) + re.findall(r'(?:src|srcset|href)="([^"]+)"', readme)
	if not links:
		raise SystemExit(f'{filename}: description has no links or images.')
	relative = [link for link in links if not link.startswith(('https://', '#'))]
	if relative:
		raise SystemExit(f'{filename}: relative or insecure description links: {relative}')
	tag = f'cookieguard-v{version}'
	roots = ('https://github.com/aiscihub/cookieguard-ai/',
		'https://raw.githubusercontent.com/aiscihub/cookieguard-ai/')
	project_links = [link for link in links if link.startswith(roots)]
	if not project_links or any(f'/{tag}/' not in link for link in project_links):
		raise SystemExit(f'{filename}: repository links must be pinned to {tag}.')
	for suffix in ('docs/policy-light.svg', 'docs/cookieguard-browser-use-demo.gif', 'docs/install.md'):
		if not any(link.endswith(suffix) for link in project_links):
			raise SystemExit(f'{filename}: missing description resource {suffix}.')
	if 'not yet on PyPI' in readme:
		raise SystemExit(f'{filename}: description still says the package is not on PyPI.')
	print(f'{filename}: {len(links)} absolute links/images; {len(project_links)} pinned to {tag}; no relative links.')


def main() -> None:
	project = tomllib.loads((HERE / 'pyproject.toml').read_text())['project']
	version = project['version']
	ref = os.environ.get('GITHUB_REF', '')
	if ref.startswith('refs/tags/') and ref != f'refs/tags/cookieguard-v{version}':
		raise SystemExit(f'Release tag {ref} does not match package version {version}.')
	# dist/ may also hold the cookieguard-browser-use compatibility files (cookieguard_browser_use-*).
	wheels = list((HERE / 'dist').glob('cookieguard-*.whl'))
	sdists = list((HERE / 'dist').glob('cookieguard-*.tar.gz'))
	if len(wheels) != 1 or len(sdists) != 1:
		raise SystemExit('Expected exactly one cookieguard wheel and one cookieguard sdist in dist/.')
	with zipfile.ZipFile(wheels[0]) as wheel:
		metadata_files = [name for name in wheel.namelist() if name.endswith('.dist-info/METADATA')]
		if len(metadata_files) != 1:
			raise SystemExit('Expected one wheel METADATA file.')
		verify(wheel.read(metadata_files[0]).decode(), wheels[0].name, version)
	with tarfile.open(sdists[0]) as sdist:
		metadata = sdist.extractfile(f'cookieguard-{version}/PKG-INFO')
		if metadata is None:
			raise SystemExit('Missing sdist PKG-INFO.')
		verify(metadata.read().decode(), sdists[0].name, version)


if __name__ == '__main__':
	main()
