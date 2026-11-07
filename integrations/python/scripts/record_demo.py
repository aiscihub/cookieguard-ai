"""Record the README demo from a real run: Browser Use agent login + CookieGuard verdict.

    python scripts/record_demo.py [--out docs] [--headed] [--provider anthropic]
    python scripts/record_demo.py --recompose    # restyle the last capture without running the agent

For each scenario (insecure, secure) this runs the real Browser Use Agent loop
against the loopback demo app, driven by the scripted stand-in model (no AI
provider) or, with --provider anthropic, by Claude. It captures:

- the agent's browser viewport, as timestamped CDP screencast frames, and its URL;
- Browser Use's own log lines for the agent's steps;
- the Set-Cookie line CookieGuard observed, with the cookie value redacted;
- the final CookieGuard result returned by audit.finish().

The side panel shows only those captured lines, at the time they happened.
Scripted model replies are paced for viewing (disclosed in the video and provenance);
pacing changes timing only. The capture is kept under artifacts/ so --recompose can
restyle it without another run. Requires ffmpeg, and npm to fetch the Geist fonts
(SIL Open Font License) on first use. Writes MP4, GIF, and provenance.json after
checking that no synthetic session token appears in any text output.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import logging
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

for key, value in (('ANONYMIZED_TELEMETRY', 'false'), ('BROWSER_USE_CLOUD_SYNC', 'false')):
	os.environ.setdefault(key, value)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent
WORK = REPO / 'artifacts' / 'browser-use' / 'recording'
CANARY_PREFIX = 'CGBU_CANARY_'
PACE_SECONDS = 1.4
IDLE_GAP, IDLE_KEEP, IDLE_VIDEO = 2.0, 0.5, 0.6  # Waits over 2s keep 0.5s at each end, middle shown in 0.6s.
FPS = 12
WIDTH, HEIGHT = 1600, 900
S = 2  # Frames are drawn at 2x and downsampled, for smooth outlines, circles, and type.
ANSI = re.compile(r'\x1b\[[0-9;]*m')
MODES = ('insecure', 'secure')

# Paper and ink, after browser-use.com, with CookieGuard blue as the accent.
PALETTE = {
	'paper': (246, 242, 234), 'card': (255, 252, 246), 'ink': (30, 25, 21), 'body': (58, 48, 41),
	'secondary': (84, 71, 60), 'quiet': (140, 124, 108), 'stroke': (193, 178, 156), 'label': (255, 250, 240),
	'accent': (47, 107, 208), 'accent-tint': (232, 239, 251), 'accent-dark': (31, 79, 163),
	'agent': (45, 130, 112), 'agent-tint': (228, 241, 237), 'browser': (176, 100, 12),
	'warn': (166, 92, 10), 'fail': (180, 35, 24), 'pass': (31, 112, 60), 'pass-icon': (43, 125, 82),
}
TONES = {'text': 'body', 'muted': 'quiet', 'warn': 'warn', 'fail': 'fail', 'pass': 'pass'}

# Geist and Geist Mono (SIL OFL 1.1, Vercel), fetched from npm at a pinned version.
GEIST = 'geist@1.5.1'
FONT_FILES = {'sans': 'geist-sans/Geist-Regular.ttf', 'sans-medium': 'geist-sans/Geist-Medium.ttf',
	'mono': 'geist-mono/GeistMono-Regular.ttf', 'mono-medium': 'geist-mono/GeistMono-Medium.ttf'}
FACES = {  # name: (font file, size in px at 1x)
	'hero': ('sans-medium', 84), 'headline': ('sans-medium', 54), 'title': ('sans-medium', 36),
	'verdict-lg': ('sans-medium', 40), 'verdict': ('sans-medium', 26), 'subtitle-lg': ('sans', 26),
	'subtitle': ('sans', 20), 'comment': ('sans', 14), 'small': ('sans', 13), 'label': ('mono-medium', 12),
	'note': ('mono', 11.5), 'log': ('mono', 13.5), 'code': ('mono', 15), 'url': ('mono', 12),
	'detail': ('mono', 14), 'pill': ('mono-medium', 17),
}

# Layout at 1x. The browser shows the 1280x720 viewport at 0.75.
BROWSER = (40, 128, 1000, 703.5)
TITLE_BAR = 34
VIEWPORT = (41.5, 162.75, 998.5, 702)
CODE_BOX = (40, 744, 1000, 862)
PANEL = (1040, 128, 1560, 862)
DIVIDER_Y = 484
VERDICT = (1062, 738, 1534, 840)


def system_font(size: float, mono: bool = False) -> ImageFont.FreeTypeFont:
	candidates = (['/System/Library/Fonts/SFNSMono.ttf', '/System/Library/Fonts/Menlo.ttc',
		'/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'] if mono else
		['/System/Library/Fonts/SFNS.ttf', '/System/Library/Fonts/Helvetica.ttc',
		'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
	for path in candidates:
		if Path(path).exists():
			return ImageFont.truetype(path, size)
	return ImageFont.load_default(size)


def geist(directory: Path) -> dict[str, Path] | None:
	"""Return the Geist font files, fetching them once with `npm pack`; None if unavailable."""
	paths = {key: directory / Path(member).name for key, member in FONT_FILES.items()}
	if all(path.exists() for path in paths.values()):
		return paths
	npm = shutil.which('npm')
	if npm is None:
		return None
	directory.mkdir(parents=True, exist_ok=True)
	packed = subprocess.run([npm, 'pack', GEIST, '--silent', '--pack-destination', str(directory)],
		capture_output=True, text=True)
	names = packed.stdout.split()
	if packed.returncode != 0 or not names or not (directory / names[-1]).is_file():
		return None
	with tarfile.open(directory / names[-1]) as archive:
		for key, member in FONT_FILES.items():
			paths[key].write_bytes(archive.extractfile(f'package/dist/fonts/{member}').read())
		(directory / 'LICENSE.TXT').write_bytes(archive.extractfile('package/LICENSE.TXT').read())
	return paths


def load_fonts(directory: Path) -> dict:
	files = geist(directory)
	if files is None:
		print('Geist fonts unavailable (npm pack failed); using system fonts.', file=sys.stderr)
	return {name: (ImageFont.truetype(str(files[kind]), round(size * S)) if files else
		system_font(round(size * S), mono=kind.startswith('mono'))) for name, (kind, size) in FACES.items()}


@dataclass
class Event:
	t: float
	lane: str  # 'agent', 'guard', or 'verdict'
	text: str
	tone: str = 'text'


@dataclass
class Capture:
	mode: str
	frames: list[tuple[float, bytes]] = field(default_factory=list)
	events: list[Event] = field(default_factory=list)
	navigations: list[tuple[float, str]] = field(default_factory=list)
	started: float = 0.0
	ended: float = 0.0
	status: str = ''
	exit_code: int = -1
	logins: int = 0
	browser: str = ''
	phases: list[float] = field(default_factory=list)


class AgentLog(logging.Handler):
	"""Keep Browser Use's own action lines, verbatim apart from color codes, emoji, and a step prefix."""

	EMOJI = re.compile(r'[\U0001F300-\U0001FAFF☀-➿️]')

	def __init__(self, capture: Capture) -> None:
		super().__init__(logging.INFO)
		self.capture = capture
		self.step = 0

	def emit(self, record: logging.LogRecord) -> None:
		text = re.sub(r'\s+', ' ', self.EMOJI.sub('', ANSI.sub('', record.getMessage()))).strip()
		step = re.match(r'Step (\d+):', text)
		if step:
			self.step = int(step.group(1))
			return
		if text.startswith('▶') and not re.match(r'▶ (\[\d+/\d+\] )?done:', text):
			text = re.sub(r'^▶ (\[\d+/\d+\] )?', '', text)
			self.capture.events.append(Event(record.created, 'agent', f'step {self.step}  {text}' if self.step else f'start   {text}'))
		elif text.startswith('Clicked button') or text.startswith('Final Result'):
			if len(text) > 170:
				text = text[:168].rstrip() + '…'
			self.capture.events.append(Event(record.created, 'agent', f'        {text}', 'muted' if text.startswith('Clicked') else 'text'))


def redact_set_cookie(line: str) -> str:
	name, _, rest = line.partition('=')
	attributes = rest.split(';', 1)[1].strip() if ';' in rest else ''
	return f'{name.strip()}=[value withheld]; {attributes}'


async def run_scenario(mode: str, headless: bool, provider: str = 'scripted', model: str | None = None) -> Capture:
	from browser_use import Agent, BrowserProfile, BrowserSession, Tools
	from cdp_use import CDPClient

	from cookieguard import CookieGuardAudit, CookiePolicyError
	from cookieguard.browser_use.demo.app import DEMO_PASSWORD, DEMO_USERNAME, DemoApp
	from cookieguard.browser_use.demo.scripted import TASK, ScriptedLoginModel

	class PacedModel(ScriptedLoginModel):
		async def ainvoke(self, messages, output_format=None, **kwargs):
			await asyncio.sleep(PACE_SECONDS)  # Viewing pace only; decisions are unchanged.
			return await super().ainvoke(messages, output_format, **kwargs)

	capture = Capture(mode)
	handler = AgentLog(capture)
	logging.getLogger('browser_use').addHandler(handler)
	token = f'{CANARY_PREFIX}{secrets.token_hex(12)}'
	try:
		with DemoApp(mode, token_factory=lambda: token) as app:
			audit = CookieGuardAudit(allowed_origins=[app.origin], auth_cookies=['session_id'])
			session = BrowserSession(browser_profile=BrowserProfile(
				headless=headless, keep_alive=True, enable_default_extensions=False, user_data_dir=None,
				viewport={'width': 1280, 'height': 720}, window_size={'width': 1280, 'height': 720},
				device_scale_factor=1.0, allowed_domains=audit.browser_allowed_domains()))
			tools = Tools()
			audit.register_tools(tools)
			recorder = None
			try:
				await session.start()
				recorder = CDPClient(session.cdp_client.url)
				await recorder.start()
				capture.browser = (await recorder.send.Browser.getVersion())['product']
				page = next(t for t in (await recorder.send.Target.getTargets())['targetInfos'] if t['type'] == 'page')
				sid = (await recorder.send.Target.attachToTarget(params={'targetId': page['targetId'], 'flatten': True}))['sessionId']

				def on_frame(event, session_id=None):
					capture.frames.append((event['metadata'].get('timestamp') or time.time(), base64.b64decode(event['data'])))
					asyncio.ensure_future(recorder.send.Page.screencastFrameAck(
						params={'sessionId': event['sessionId']}, session_id=sid))

				def on_navigated(event, session_id=None):
					if not event['frame'].get('parentId'):  # Main frame only; shown in the browser's URL bar.
						capture.navigations.append((time.time(), event['frame']['url']))

				recorder.register.Page.screencastFrame(on_frame)
				recorder.register.Page.frameNavigated(on_navigated)
				await recorder.send.Page.enable(session_id=sid)
				await recorder.send.Page.startScreencast(params={'format': 'jpeg', 'quality': 85, 'maxWidth': 1280,
					'maxHeight': 720, 'everyNthFrame': 1}, session_id=sid)
				capture.started = time.time()
				capture.phases.append(time.time())
				await audit.start(session)
				capture.events.append(Event(time.time(), 'guard', 'audit.start(session): observing the agent’s browser', 'muted'))
				engine = audit._engine
				original = engine.response

				async def observed(url, lines, from_service_worker):
					for line in lines:
						capture.events.append(Event(time.time(), 'guard', f'Set-Cookie observed: {redact_set_cookie(line)}', 'warn'))
					await original(url, lines, from_service_worker)

				engine.response = observed  # Instrumentation: records what was forwarded, never the value.
				agent_check = audit._agent_check

				async def checked(browser_session):
					text = await agent_check(browser_session)
					capture.events.append(Event(time.time(), 'agent', f'        tool result: {text.splitlines()[0]}', 'muted'))
					return text

				audit._agent_check = checked  # Instrumentation: records the agent-visible result when returned.
				if provider == 'anthropic':
					from browser_use import ChatAnthropic
					# Same settings as examples/agent_login.py (verified): adaptive thinking, server-side fallback.
					llm = ChatAnthropic(model=model, thinking={'type': 'adaptive'}, fallbacks=[{'model': 'claude-opus-4-8'}])
				else:
					llm = PacedModel(app.origin)
				agent = Agent(task=TASK.format(origin=app.origin), llm=llm, browser_session=session,
					tools=tools, use_vision=False, use_judge=False, calculate_cost=False, max_actions_per_step=4,
					sensitive_data={audit.browser_allowed_domains()[0]: {'login_user': DEMO_USERNAME, 'login_password': DEMO_PASSWORD}})
				capture.phases.append(time.time())
				await agent.run(max_steps=8)
				capture.phases.append(time.time())
				result = await audit.finish()
				now = time.time()
				capture.phases.append(now + 0.8)
				capture.status, capture.exit_code, capture.logins = result.status, result.exit_code, app.logins
				capture.events.append(Event(now, 'guard', f'audit.finish(): server login accepted ({app.logins}); evaluating', 'muted'))
				for finding in result.confirmed_findings:
					capture.events.append(Event(now + 0.4, 'guard',
						f'{finding.rule_id} {finding.severity} confirmed: {finding.title} ({finding.cookie_name})', 'fail'))
				try:
					result.assert_policy()
					capture.events.append(Event(now + 0.8, 'guard', 'result.assert_policy(): passed', 'pass'))
				except CookiePolicyError as error:
					capture.events.append(Event(now + 0.8, 'guard', f'result.assert_policy(): {type(error).__name__}', 'fail'))
				capture.events.append(Event(now + 1.2, 'verdict', f'{result.status} · exit {result.exit_code}',
					'fail' if result.status != 'PASS' else 'pass'))
				await asyncio.sleep(0.5)
				capture.ended = time.time() + 3.5
			finally:
				if recorder is not None:
					try:
						await recorder.stop()
					except Exception:
						pass
				await audit.close()
				await session.kill()
	finally:
		logging.getLogger('browser_use').removeHandler(handler)
	text = json.dumps([e.text for e in capture.events] + [url for _, url in capture.navigations])
	api_key = os.environ.get('ANTHROPIC_API_KEY', '')
	if CANARY_PREFIX in text or token in text or DEMO_PASSWORD in text or (api_key and api_key in text):
		raise SystemExit('Sensitive value found in captured text; recording withheld.')
	if not capture.frames:
		raise SystemExit('No screencast frames captured.')
	return capture


def save_captures(captures: list[Capture], recording: dict, work: Path) -> None:
	"""Keep the raw capture (browser frames and timed lines) so the video can be restyled without a rerun."""
	root = work / 'capture'
	shutil.rmtree(root, ignore_errors=True)
	for capture in captures:
		frames = root / capture.mode / 'frames'
		frames.mkdir(parents=True)
		for i, (_, data) in enumerate(capture.frames):
			(frames / f'{i:05d}.jpg').write_bytes(data)
		meta = {key: value for key, value in asdict(capture).items() if key != 'frames'}
		meta['frameTimes'] = [t for t, _ in capture.frames]
		(root / capture.mode / 'capture.json').write_text(json.dumps(meta, ensure_ascii=False))
	(root / 'recording.json').write_text(json.dumps(recording, indent=2, ensure_ascii=False) + '\n')


def load_captures(work: Path) -> tuple[list[Capture], dict]:
	root = work / 'capture'
	if not (root / 'recording.json').is_file():
		raise SystemExit(f'No saved capture in {root}; run without --recompose first.')
	captures = []
	for mode in MODES:
		meta = json.loads((root / mode / 'capture.json').read_text())
		times = meta.pop('frameTimes')
		capture = Capture(**{**meta, 'events': [Event(**e) for e in meta['events']],
			'navigations': [tuple(n) for n in meta['navigations']]})
		capture.frames = [(t, (root / mode / 'frames' / f'{i:05d}.jpg').read_bytes()) for i, t in enumerate(times)]
		captures.append(capture)
	return captures, json.loads((root / 'recording.json').read_text())


TITLES = {
	'insecure': ('Insecure login', 'The app’s session cookie omits HttpOnly.'),
	'secure': ('Secure login', 'Same app and agent, with HttpOnly set.'),
}


CODE = [
	('await audit.start(session)', 'CookieGuard starts observing the agent’s browser'),
	('await agent.run()', 'the Browser Use agent logs in'),
	('result = await audit.finish()', 'the local CookieGuard engine decides'),
	('result.assert_policy()', 'your test enforces it, not the agent'),
]


class Canvas:
	"""A 2x drawing surface addressed in 1x coordinates; text is placed by its baseline."""

	def __init__(self, fonts: dict, base: Image.Image | None = None) -> None:
		self.image = base.copy() if base is not None else Image.new('RGB', (WIDTH * S, HEIGHT * S), PALETTE['paper'])
		self.draw = ImageDraw.Draw(self.image)
		self.fonts = fonts

	def width(self, text: str, face: str, tracking: float = 0.0) -> float:
		return self.draw.textlength(text, font=self.fonts[face]) / S + tracking * max(len(text) - 1, 0)

	def text(self, x: float, y: float, text: str, face: str, color: str = 'ink', tracking: float = 0.0) -> float:
		"""Draw text with its baseline at y and return the x where it ends."""
		typeface, fill = self.fonts[face], PALETTE[color]
		if tracking:
			for i, char in enumerate(text):
				offset = self.draw.textlength(text[:i], font=typeface) + i * tracking * S
				self.draw.text((x * S + offset, y * S), char, font=typeface, fill=fill, anchor='ls')
		else:
			self.draw.text((x * S, y * S), text, font=typeface, fill=fill, anchor='ls')
		return x + self.width(text, face, tracking)

	def rect(self, box, radius: float = 0, fill: str | None = None, outline: str | None = None, width: float = 1.5) -> None:
		self.draw.rounded_rectangle([v * S for v in box], radius * S, fill=PALETTE[fill] if fill else None,
			outline=PALETTE[outline] if outline else None, width=round(width * S))

	def card(self, box, radius: float = 10, fill: str = 'card', offset: float = 5) -> None:
		"""An ink-outlined card with a second outline offset behind it."""
		if offset:
			x0, y0, x1, y1 = box
			self.rect((x0 + offset, y0 + offset, x1 + offset, y1 + offset), radius, 'card', 'ink')
		self.rect(box, radius, fill, 'ink')

	def line(self, x0: float, y0: float, x1: float, y1: float, color: str = 'ink', width: float = 1.5) -> None:
		self.draw.line((x0 * S, y0 * S, x1 * S, y1 * S), fill=PALETTE[color], width=round(width * S))

	def dashed(self, x0: float, y0: float, x1: float, y1: float, color: str = 'stroke', dash: float = 5, gap: float = 4) -> None:
		length = math.hypot(x1 - x0, y1 - y0)
		ux, uy = (x1 - x0) / length, (y1 - y0) / length
		position = 0.0
		while position < length:
			end = min(position + dash, length)
			self.line(x0 + ux * position, y0 + uy * position, x0 + ux * end, y0 + uy * end, color)
			position = end + gap

	def arrow(self, x0: float, x1: float, y: float, color: str = 'secondary') -> None:
		"""A dashed horizontal connector with an open chevron at x1."""
		self.dashed(x0, y, x1, y, color, dash=3, gap=3)
		d = 5 if x1 > x0 else -5
		self.draw.line([((x1 - d) * S, (y - 5) * S), (x1 * S, y * S), ((x1 - d) * S, (y + 5) * S)],
			fill=PALETTE[color], width=round(1.5 * S), joint='curve')

	def circle(self, cx: float, cy: float, r: float, fill: str | None = None, outline: str | None = None, width: float = 1.5) -> None:
		self.draw.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), fill=PALETTE[fill] if fill else None,
			outline=PALETTE[outline] if outline else None, width=round(width * S))

	def label(self, x: float, y: float, text: str, square: str, aside: str = '') -> None:
		"""A small uppercase mono label after a colored square, baseline at y."""
		self.rect((x, y - 9, x + 8, y - 1), 0, square)
		end = self.text(x + 15, y, text.upper(), 'label', 'secondary', tracking=0.9)
		if aside:
			self.text(end + 10, y, aside, 'small', 'quiet')

	def mark(self, cx: float, cy: float, r: float, passed: bool) -> None:
		"""A filled circle with a check (PASS) or a cross (anything else)."""
		self.circle(cx, cy, r, 'pass-icon' if passed else 'fail')
		width = max(2, round(r * 0.2 * S))
		if passed:
			points = [(cx - 0.42 * r, cy + 0.02 * r), (cx - 0.12 * r, cy + 0.33 * r), (cx + 0.45 * r, cy - 0.3 * r)]
			self.draw.line([(px * S, py * S) for px, py in points], fill=PALETTE['card'], width=width, joint='curve')
		else:
			d = 0.32 * r
			for sign in (1, -1):
				self.draw.line(((cx - d) * S, (cy - sign * d) * S, (cx + d) * S, (cy + sign * d) * S), fill=PALETTE['card'], width=width)

	def play(self, x: float, y: float, size: float, color: str) -> None:
		"""A right-pointing triangle with its left edge at x, centered on y."""
		self.draw.polygon([(x * S, (y - size / 2) * S), (x * S, (y + size / 2) * S), ((x + size * 0.87) * S, y * S)],
			fill=PALETTE[color])

	def paste(self, picture: Image.Image, box, mask: Image.Image | None = None) -> None:
		x0, y0, x1, y1 = (round(v * S) for v in box)
		self.image.paste(picture.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0), mask)

	def centered(self, y: float, text: str, face: str, color: str = 'ink', tracking: float = 0.0) -> None:
		self.text((WIDTH - self.width(text, face, tracking)) / 2, y, text, face, color, tracking)

	def finish(self) -> Image.Image:
		return self.image.resize((WIDTH, HEIGHT), Image.LANCZOS)


def viewport_mask() -> Image.Image:
	"""Square top corners under the title bar, rounded bottom corners inside the card outline."""
	x0, y0, x1, y1 = (round(v * S) for v in VIEWPORT)
	mask = Image.new('L', (x1 - x0, y1 - y0), 0)
	draw = ImageDraw.Draw(mask)
	draw.rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), round(8.5 * S), fill=255)
	draw.rectangle((0, 0, x1 - x0 - 1, (y1 - y0) // 2), fill=255)
	return mask


def wrap(canvas: Canvas, text: str, face: str, width: float) -> list[str]:
	lines, current = [], ''
	for word in text.split(' '):
		trial = f'{current} {word}' if current else word
		if canvas.width(trial, face) <= width or not current:
			current = trial
		else:
			lines.append(current)
			current = '  ' + word
	return lines + [current] if current else lines


def lane(canvas: Canvas, capture: Capture, name: str, t: float, top: float, bottom: float, x: float, width: float) -> None:
	"""Draw a lane's events that have happened by time t, newest at the bottom, oldest dropped to fit."""
	blocks = [(wrap(canvas, e.text, 'log', width), TONES[e.tone]) for e in capture.events if e.lane == name and e.t <= t]
	line_height, gap = 19, 7
	while blocks and sum(len(rows) * line_height + gap for rows, _ in blocks) - gap > bottom - top:
		blocks.pop(0)
	y = top + 14
	for rows, color in blocks:
		for row in rows:
			canvas.text(x, y, row, 'log', color)
			y += line_height
		y += gap


def static_layer(capture: Capture, number: int, note: str, fonts: dict) -> Image.Image:
	"""Everything in a scenario frame that does not change over time."""
	c = Canvas(fonts)
	title, subtitle = TITLES[capture.mode]
	c.label(40, 40, f'Scenario {number} of {len(MODES)}', 'accent')
	end = c.text(40, 82, title, 'title', 'ink', tracking=-1.1)
	c.text(end + 16, 82, subtitle, 'subtitle', 'secondary')
	text = note.upper()
	w = c.width(text, 'note', 0.6)
	c.rect((WIDTH - 40 - w - 30, 58, WIDTH - 40, 88), 15, 'card', 'ink', 1.2)
	c.text(WIDTH - 40 - w - 15, 77.5, text, 'note', 'secondary', 0.6)

	x0, y0, x1, _ = BROWSER
	c.label(x0, 114, 'Chromium · driven by the Browser Use agent', 'browser')
	c.card(BROWSER)
	c.line(x0, y0 + TITLE_BAR, x1, y0 + TITLE_BAR)
	cy = y0 + TITLE_BAR / 2
	c.circle(x0 + 20, cy, 5, 'ink')
	for dx in (36, 52):
		c.circle(x0 + dx, cy, 5, None, 'ink', 1.3)

	c.label(CODE_BOX[0], 732, 'Your test', 'accent')
	c.card(CODE_BOX)

	px0, py0, px1, _ = PANEL
	c.card(PANEL)
	c.label(px0 + 22, py0 + 30, 'Browser Use agent', 'agent', aside='its own log lines')
	c.dashed(px0 + 22, DIVIDER_Y, px1 - 22, DIVIDER_Y)
	c.label(px0 + 22, DIVIDER_Y + 30, 'CookieGuard', 'accent', aside='in your test code')
	# The agent drives the browser; CookieGuard observes the same browser over its own CDP connection.
	c.arrow(px0 - 6, BROWSER[2] + 10, py0 + 26)
	c.arrow(BROWSER[2] + 10, px0 - 6, DIVIDER_Y + 26)
	return c.image


def verdict_detail(capture: Capture, passed: bool) -> str:
	if passed:
		return 'no confirmed violations · assert_policy() passed'
	finding = next((e.text for e in capture.events if e.lane == 'guard' and e.tone == 'fail' and e.text.startswith('CG')), None)
	return finding or 'assert_policy() raised CookiePolicyError'


def render(capture: Capture, t: float, browser: Image.Image | None, fonts: dict, base: Image.Image, mask: Image.Image,
		fast: bool = False) -> Image.Image:
	c = Canvas(fonts, base)
	x0, y0, _, _ = BROWSER
	url = next((u for when, u in reversed(capture.navigations) if when <= t), 'about:blank')
	cy = y0 + TITLE_BAR / 2
	c.rect((x0 + 70, cy - 11, x0 + 470, cy + 11), 11, 'card', 'ink', 1.2)
	c.text(x0 + 84, cy + 4, re.sub(r'^https?://', '', url), 'url', 'ink')
	if browser is not None:
		c.paste(browser, VIEWPORT, mask)
	if fast:
		label = 'FAST-FORWARD · WAITING FOR THE MODEL'
		w = c.width(label, 'label', 0.9)
		bx1, by0 = VIEWPORT[2] - 14, VIEWPORT[1] + 14
		bx0 = bx1 - w - 56
		c.rect((bx0, by0, bx1, by0 + 28), 14, 'accent-tint', 'accent', 1.2)
		c.play(bx0 + 14, by0 + 14, 9, 'accent')
		c.play(bx0 + 22, by0 + 14, 9, 'accent')
		c.text(bx0 + 40, by0 + 18.5, label, 'label', 'accent-dark', 0.9)

	# The code that is running, highlighted from real phase timestamps.
	phase = max([i for i, start in enumerate(capture.phases) if start <= t], default=0)
	for i, (code, comment) in enumerate(CODE):
		baseline = CODE_BOX[1] + 28 + i * 24
		active = i == phase
		if active:
			agent_line = i == 1
			c.rect((CODE_BOX[0] + 8, baseline - 17, CODE_BOX[2] - 8, baseline + 7), 6, 'agent-tint' if agent_line else 'accent-tint')
			c.play(CODE_BOX[0] + 20, baseline - 5, 10, 'agent' if agent_line else 'accent')
		c.text(CODE_BOX[0] + 40, baseline, code, 'code', 'ink' if active else 'quiet')
		c.text(CODE_BOX[0] + 440, baseline, f'# {comment}', 'comment', 'secondary' if active else 'quiet')

	px0, py0, px1, py1 = PANEL
	verdict = next((e for e in reversed(capture.events) if e.lane == 'verdict' and e.t <= t), None)
	lane(c, capture, 'agent', t, py0 + 44, DIVIDER_Y - 14, px0 + 22, px1 - px0 - 44)
	lane(c, capture, 'guard', t, DIVIDER_Y + 44, (VERDICT[1] - 14) if verdict else py1 - 18, px0 + 22, px1 - px0 - 44)
	if verdict is not None:
		passed = verdict.tone == 'pass'
		vx0, vy0, vx1, _ = VERDICT
		c.card(VERDICT, 10, 'card', 4)
		c.mark(vx0 + 36, vy0 + 33, 15, passed)
		status, _, rest = verdict.text.partition(' ')
		end = c.text(vx0 + 62, vy0 + 42, status, 'verdict', 'pass' if passed else 'fail', -0.5)
		c.text(end + 7, vy0 + 42, rest, 'verdict', 'ink', -0.5)
		c.dashed(vx0 + 22, vy0 + 62, vx1 - 22, vy0 + 62)
		c.text(vx0 + 22, vy0 + 86, verdict_detail(capture, passed), 'detail', 'secondary')
	return c.finish()


def title_card(capture: Capture, number: int, fonts: dict) -> Image.Image:
	c = Canvas(fonts)
	title, subtitle = TITLES[capture.mode]
	label = f'Scenario {number} of {len(MODES)}'
	c.label((WIDTH - c.width(label.upper(), 'label', 0.9) - 15) / 2, 352, label, 'accent')
	c.centered(452, title, 'hero', 'ink', -2.9)
	c.centered(508, subtitle, 'subtitle-lg', 'secondary')
	return c.finish()


def end_card(captures: list[Capture], fonts: dict) -> Image.Image:
	c = Canvas(fonts)
	c.centered(218, 'Same agent, same successful login.', 'headline', 'ink', -1.8)
	c.centered(282, 'Different cookie, different result.', 'headline', 'ink', -1.8)
	for i, capture in enumerate(captures):
		x = 270 + i * 560
		passed = capture.status == 'PASS'
		c.label(x, 362, f'Scenario {i + 1} · {TITLES[capture.mode][0]}', 'pass-icon' if passed else 'fail')
		c.card((x, 376, x + 500, 566))
		c.mark(x + 44, 426, 20, passed)
		end = c.text(x + 76, 440, capture.status, 'verdict-lg', 'pass' if passed else 'fail', -1.0)
		c.text(end + 10, 440, f'· exit {capture.exit_code}', 'verdict-lg', 'ink', -1.0)
		c.dashed(x + 24, 474, x + 476, 474)
		rules = ', '.join(sorted({e.text.split(' ')[0] for e in capture.events
			if e.lane == 'guard' and e.tone == 'fail' and e.text.startswith('CG')}))
		for j, (key, value) in enumerate((('agent login accepted by the server', 'yes' if capture.logins else 'no'),
				('confirmed violations', rules or 'none'))):
			c.text(x + 24, 508 + j * 30, key, 'detail', 'secondary')
			c.text(x + 476 - c.width(value, 'detail'), 508 + j * 30, value, 'detail', 'ink')
	install, demo = 'pip install cookieguard', 'python -m cookieguard.browser_use.demo'
	wa, wb = c.width(install, 'pill') + 52, c.width(demo, 'pill') + 52
	x = (WIDTH - wa - 16 - wb) / 2
	c.rect((x, 640, x + wa, 690), 25, 'accent')
	c.text(x + 26, 671, install, 'pill', 'label')
	c.rect((x + wa + 16, 640, x + wa + 16 + wb, 690), 25, 'card', 'ink')
	c.text(x + wa + 42, 671, demo, 'pill', 'ink')
	c.centered(744, 'github.com/aiscihub/cookieguard-ai', 'detail', 'quiet')
	return c.finish()


def sample_times(start: float, end: float, marks: list[float], compress_until: float) -> list[tuple[float, bool]]:
	"""Real-time samples, except long idle gaps (no page change, no log line), which are condensed and flagged."""
	step, samples, t, previous = 1 / FPS, [], start, start
	for mark in sorted({m for m in marks if start < m < end}) + [end]:
		if mark - previous > IDLE_GAP and mark <= compress_until:  # Never condense the final hold.
			a, b = previous + IDLE_KEEP, mark - IDLE_KEEP
			while t < a:
				samples.append((t, False))
				t += step
			count = int(FPS * IDLE_VIDEO)
			samples += [(a + (b - a) * i / count, True) for i in range(count)]
			t = b
		previous = mark
	while t <= end:
		samples.append((t, False))
		t += step
	return samples


def compose(captures: list[Capture], note: str, out: Path, work: Path) -> dict:
	fonts = load_fonts(work / 'fonts')
	mask = viewport_mask()
	frames_dir = work / 'composite'
	shutil.rmtree(frames_dir, ignore_errors=True)
	frames_dir.mkdir(parents=True)
	index = 0
	for number, capture in enumerate(captures, 1):
		card = title_card(capture, number, fonts)
		for _ in range(int(FPS * 1.6)):
			card.save(frames_dir / f'{index:05d}.png')
			index += 1
		base = static_layer(capture, number, note, fonts)
		start, end = capture.frames[0][0], capture.ended
		decoded: dict[int, Image.Image] = {}
		position = 0
		marks = [frame[0] for frame in capture.frames] + [event.t for event in capture.events]
		verdict_t = next(e.t for e in capture.events if e.lane == 'verdict')
		for t, fast in sample_times(start, end, marks, verdict_t):
			while position + 1 < len(capture.frames) and capture.frames[position + 1][0] <= t:
				position += 1
			if position not in decoded:
				decoded.clear()
				decoded[position] = Image.open(io.BytesIO(capture.frames[position][1])).convert('RGB')
			render(capture, t, decoded[position], fonts, base, mask, fast).save(frames_dir / f'{index:05d}.png')
			index += 1
	card = end_card(captures, fonts)
	for _ in range(int(FPS * 3.5)):
		card.save(frames_dir / f'{index:05d}.png')
		index += 1
	out.mkdir(parents=True, exist_ok=True)
	mp4, gif = out / 'cookieguard-browser-use-demo.mp4', out / 'cookieguard-browser-use-demo.gif'
	subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(frames_dir / '%05d.png'),
		'-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', str(mp4)], check=True)
	subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(frames_dir / '%05d.png'),
		'-vf', 'fps=10,scale=1000:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];'
		'[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle', '-loop', '0', str(gif)], check=True)
	return {'frames': index, 'mp4': mp4, 'gif': gif}


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument('--out', default=str(HERE / 'docs'))
	parser.add_argument('--headed', action='store_true')
	parser.add_argument('--provider', choices=['scripted', 'anthropic'], default='scripted')
	parser.add_argument('--model', default='claude-opus-5-5', help='model id for --provider anthropic')
	parser.add_argument('--recompose', action='store_true',
		help='rebuild the video from the last saved capture instead of running the agent')
	args = parser.parse_args()
	if not shutil.which('ffmpeg'):
		raise SystemExit('ffmpeg is required.')
	WORK.mkdir(parents=True, exist_ok=True)
	if args.recompose:
		captures, recording = load_captures(WORK)
	else:
		if args.provider == 'anthropic' and not os.environ.get('ANTHROPIC_API_KEY'):
			raise SystemExit('ANTHROPIC_API_KEY is not set.')
		captures = [asyncio.run(run_scenario(mode, headless=not args.headed, provider=args.provider, model=args.model))
			for mode in MODES]
		recording = {
			'recordedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
			'note': (f'Real run · {args.model} drives the agent · long waits sped up' if args.provider == 'anthropic'
				else 'Real run · scripted model paced for viewing'),
			'model': ('scripted stand-in (no AI provider); replies paced by %.1fs for viewing' % PACE_SECONDS
				if args.provider == 'scripted' else
				f'{args.model} via browser_use.ChatAnthropic (adaptive thinking; server-side fallback to claude-opus-4-8)'),
		}
	expected = {'insecure': ('FAIL', 1), 'secure': ('PASS', 0)}
	for capture in captures:
		if (capture.status, capture.exit_code) != expected[capture.mode] or capture.logins != 1:
			raise SystemExit(f'Unexpected result for {capture.mode}; recording withheld.')
	if not args.recompose:
		save_captures(captures, recording, WORK)
	outputs = compose(captures, recording['note'], Path(args.out), WORK)
	provenance = {
		'recordedAt': recording['recordedAt'], 'browser': captures[0].browser, 'model': recording['model'],
		'timing': f'idle gaps over {IDLE_GAP}s (no page change or log line) keep {IDLE_KEEP}s at each end; '
			f'the rest is condensed to {IDLE_VIDEO}s and labelled fast-forward',
		'scenarios': [{'mode': c.mode, 'status': c.status, 'exitCode': c.exit_code, 'serverLogins': c.logins,
			'screencastFrames': len(c.frames), 'seconds': round(c.ended - c.frames[0][0], 1),
			'panelLines': [{'t': round(e.t - c.frames[0][0], 2), 'lane': e.lane, 'text': e.text} for e in c.events]}
			for c in captures],
		'outputs': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (outputs['mp4'], outputs['gif'])},
		'compositeFrames': outputs['frames'],
	}
	text = json.dumps(provenance, indent=2, ensure_ascii=False) + '\n'
	api_key = os.environ.get('ANTHROPIC_API_KEY', '')
	if CANARY_PREFIX in text or (api_key and api_key in text):
		raise SystemExit('Sensitive value found in provenance; withheld.')
	(WORK / 'provenance.json').write_text(text)
	(Path(args.out) / 'demo-provenance.json').write_text(text)
	for path in (outputs['mp4'], outputs['gif']):
		print(f'{path}: {path.stat().st_size / 1e6:.1f} MB')
	print(f'Provenance: {Path(args.out) / "demo-provenance.json"}')
	return 0


if __name__ == '__main__':
	sys.exit(main())
