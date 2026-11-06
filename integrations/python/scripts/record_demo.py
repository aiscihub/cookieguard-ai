"""Record the README demo from a real run: Browser Use agent login + CookieGuard verdict.

    python scripts/record_demo.py [--out docs] [--headed]

For each scenario (insecure, secure) this runs the real Browser Use Agent loop
against the loopback demo app, driven by the scripted stand-in model (no AI
provider). It captures:

- the agent's browser viewport, as timestamped CDP screencast frames;
- Browser Use's own log lines for the agent's steps;
- the Set-Cookie line CookieGuard observed, with the cookie value redacted;
- the final CookieGuard result returned by audit.finish().

The side panel shows only those captured lines, at the time they happened.
Model replies are paced for viewing (disclosed in the video and provenance);
pacing changes timing only. Requires ffmpeg. Writes MP4, GIF, and provenance.json
after checking that no synthetic session token appears in any text output.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

for key, value in (('ANONYMIZED_TELEMETRY', 'false'), ('BROWSER_USE_CLOUD_SYNC', 'false')):
	os.environ.setdefault(key, value)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent
CANARY_PREFIX = 'CGBU_CANARY_'
PACE_SECONDS = 1.4
IDLE_GAP, IDLE_KEEP, IDLE_VIDEO = 2.0, 0.5, 0.6  # Waits over 2s keep 0.5s at each end, middle shown in 0.6s.
NOTE = 'Real run · scripted model paced for viewing'
FPS = 12
WIDTH, HEIGHT = 1600, 900
BROWSER_BOX = (32, 132, 32 + 960, 132 + 540)  # 1280x720 viewport scaled by 0.75  # 1280x720 viewport scaled by 0.8
PANEL_X = BROWSER_BOX[2] + 32
ANSI = re.compile(r'\x1b\[[0-9;]*m')

COLORS = {
	'bg': (14, 17, 23), 'panel': (22, 27, 34), 'border': (48, 54, 61), 'text': (230, 237, 243),
	'muted': (139, 148, 158), 'agent': (121, 192, 255), 'guard': (210, 168, 255), 'fail': (248, 81, 73),
	'pass': (63, 185, 80), 'warn': (210, 153, 34),
}


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
	candidates = (['/System/Library/Fonts/SFNSMono.ttf', '/System/Library/Fonts/Menlo.ttc',
		'/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'] if mono else
		['/System/Library/Fonts/SFNS.ttf', '/System/Library/Fonts/Helvetica.ttc',
		'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
	for path in candidates:
		if Path(path).exists():
			return ImageFont.truetype(path, size)
	return ImageFont.load_default(size)


@dataclass
class Event:
	t: float
	lane: str  # 'agent' or 'guard'
	text: str
	tone: str = 'text'


@dataclass
class Capture:
	mode: str
	frames: list[tuple[float, bytes]] = field(default_factory=list)
	events: list[Event] = field(default_factory=list)
	started: float = 0.0
	ended: float = 0.0
	status: str = ''
	exit_code: int = -1
	logins: int = 0
	browser: str = ''
	phases: list[float] = field(default_factory=list)
	logins_by_mode: dict = field(default_factory=dict)


class AgentLog(logging.Handler):
	"""Keep Browser Use's own action lines, verbatim apart from color codes, emoji, and a step prefix."""

	EMOJI = re.compile(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]')

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

				recorder.register.Page.screencastFrame(on_frame)
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
	text = json.dumps([e.text for e in capture.events])
	api_key = os.environ.get('ANTHROPIC_API_KEY', '')
	if CANARY_PREFIX in text or token in text or DEMO_PASSWORD in text or (api_key and api_key in text):
		raise SystemExit('Sensitive value found in captured text; recording withheld.')
	if not capture.frames:
		raise SystemExit('No screencast frames captured.')
	return capture


TITLES = {
	'insecure': ('1 · Insecure login', 'The app’s session cookie omits HttpOnly.'),
	'secure': ('2 · Secure login', 'Same app and agent, with HttpOnly set.'),
}


CODE = [
	('await audit.start(session)', 'CookieGuard starts observing the agent’s browser'),
	('await agent.run()', 'the Browser Use agent logs in'),
	('result = await audit.finish()', 'the local CookieGuard engine decides'),
	('result.assert_policy()', 'your test enforces it, not the agent'),
]


def wrap(draw: ImageDraw.ImageDraw, text: str, typeface, width: int) -> list[str]:
	lines, current = [], ''
	for word in text.split(' '):
		trial = f'{current} {word}' if current else word
		if draw.textlength(trial, font=typeface) <= width or not current:
			current = trial
		else:
			lines.append(current)
			current = '  ' + word
	return lines + [current] if current else lines


def lane(draw, capture: Capture, name: str, t: float, top: int, bottom: int, x: int, width: int, fonts: dict) -> None:
	"""Draw a lane's events that have happened by time t, newest at the bottom, oldest dropped to fit."""
	blocks = []
	for event in (e for e in capture.events if e.lane == name and e.t <= t):
		blocks.append((wrap(draw, event.text, fonts['mono'], width), COLORS[event.tone]))
	line_height, gap = 21, 7
	while blocks and sum(len(rows) * line_height + gap for rows, _ in blocks) > bottom - top:
		blocks.pop(0)
	y = top
	for rows, color in blocks:
		for row in rows:
			draw.text((x, y), row, font=fonts['mono'], fill=color)
			y += line_height
		y += gap


def render(capture: Capture, t: float, browser: Image.Image | None, fonts: dict, fast: bool = False) -> Image.Image:
	image = Image.new('RGB', (WIDTH, HEIGHT), COLORS['bg'])
	draw = ImageDraw.Draw(image)
	title, subtitle = TITLES[capture.mode]
	draw.text((32, 30), title, font=fonts['title'], fill=COLORS['text'])
	draw.text((32 + draw.textlength(title, font=fonts['title']) + 18, 40), subtitle, font=fonts['sub'], fill=COLORS['muted'])
	note = NOTE
	draw.text((WIDTH - 32 - draw.textlength(note, font=fonts['caption']), 44), note, font=fonts['caption'], fill=COLORS['muted'])
	x0, y0, x1, y1 = BROWSER_BOX
	draw.rounded_rectangle((x0 - 2, y0 - 30, x1 + 2, y1 + 2), 10, fill=COLORS['panel'], outline=COLORS['border'], width=2)
	for i, dot in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
		draw.ellipse((x0 + 12 + i * 20, y0 - 21, x0 + 24 + i * 20, y0 - 9), fill=dot)
	draw.text((x0 + 84, y0 - 24), 'Chromium · driven by the Browser Use agent', font=fonts['caption'], fill=COLORS['muted'])
	if browser is not None:
		image.paste(browser.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
	if fast:
		label = '▶▶  fast-forward: waiting for the model'
		w = draw.textlength(label, font=fonts['lane'])
		draw.rounded_rectangle((x1 - w - 36, y0 + 12, x1 - 12, y0 + 42), 8, fill=(33, 46, 66), outline=COLORS['agent'], width=2)
		draw.text((x1 - w - 24, y0 + 18), label, font=fonts['lane'], fill=COLORS['agent'])
	# Developer code, with the line that is running highlighted from real phase timestamps.
	phase = max([i for i, start in enumerate(capture.phases) if start <= t], default=0)
	cy = y1 + 22
	draw.rounded_rectangle((x0 - 2, cy, x1 + 2, HEIGHT - 32), 10, fill=COLORS['panel'], outline=COLORS['border'], width=2)
	for i, (code, comment) in enumerate(CODE):
		y = cy + 16 + i * 34
		active = i == phase
		if active:
			draw.rounded_rectangle((x0 + 8, y - 5, x1 - 8, y + 27), 6, fill=(33, 46, 66))
			draw.text((x0 + 16, y), '▶', font=fonts['code'], fill=COLORS['agent'] if i == 1 else COLORS['guard'])
		draw.text((x0 + 44, y), code, font=fonts['code'], fill=COLORS['text'] if active else COLORS['muted'])
		draw.text((x0 + 470, y + 2), f'# {comment}', font=fonts['comment'], fill=COLORS['muted'] if active else (88, 96, 105))
	px, pw = PANEL_X, WIDTH - PANEL_X - 32
	draw.rounded_rectangle((px, y0 - 30, px + pw, HEIGHT - 32), 10, fill=COLORS['panel'], outline=COLORS['border'], width=2)
	verdict = next((e for e in reversed(capture.events) if e.lane == 'verdict' and e.t <= t), None)
	verdict_top = HEIGHT - 32 - 96
	draw.text((px + 20, y0 - 18), 'BROWSER USE AGENT  (its own log lines)', font=fonts['lane'], fill=COLORS['agent'])
	lane(draw, capture, 'agent', t, y0 + 12, y0 + 360, px + 20, pw - 40, fonts)
	gy = y0 + 378
	draw.line((px + 20, gy, px + pw - 20, gy), fill=COLORS['border'], width=1)
	draw.text((px + 20, gy + 12), 'COOKIEGUARD  (in your test code)', font=fonts['lane'], fill=COLORS['guard'])
	lane(draw, capture, 'guard', t, gy + 42, (verdict_top - 12) if verdict else HEIGHT - 48, px + 20, pw - 40, fonts)
	if verdict is not None:
		color = COLORS[verdict.tone]
		box = (px + 20, verdict_top, px + pw - 20, HEIGHT - 52)
		draw.rounded_rectangle(box, 10, fill=tuple(int(c * 0.2) for c in color), outline=color, width=3)
		label = f'CookieGuard: {verdict.text}'
		w = draw.textlength(label, font=fonts['verdict'])
		draw.text(((box[0] + box[2] - w) / 2, box[1] + 14), label, font=fonts['verdict'], fill=color)
	return image


def title_card(capture: Capture, fonts: dict) -> Image.Image:
	image = Image.new('RGB', (WIDTH, HEIGHT), COLORS['bg'])
	draw = ImageDraw.Draw(image)
	title, subtitle = TITLES[capture.mode]
	for text, typeface, color, dy in ((title, fonts['card'], COLORS['text'], -40), (subtitle, fonts['sub'], COLORS['muted'], 40)):
		w = draw.textlength(text, font=typeface)
		draw.text(((WIDTH - w) / 2, HEIGHT / 2 + dy - 20), text, font=typeface, fill=color)
	return image


def end_card(captures: list[Capture], fonts: dict) -> Image.Image:
	image = Image.new('RGB', (WIDTH, HEIGHT), COLORS['bg'])
	draw = ImageDraw.Draw(image)
	heading = 'Same agent, same successful login. Different cookie, different result.'
	draw.text(((WIDTH - draw.textlength(heading, font=fonts['sub'])) / 2, 250), heading, font=fonts['sub'], fill=COLORS['muted'])
	for i, capture in enumerate(captures):
		x = 200 + i * 640
		color = COLORS['pass'] if capture.status == 'PASS' else COLORS['fail']
		draw.rounded_rectangle((x, 330, x + 560, 560), 14, fill=COLORS['panel'], outline=color, width=3)
		draw.text((x + 32, 356), TITLES[capture.mode][0], font=fonts['title'], fill=COLORS['text'])
		draw.text((x + 32, 410), f'Agent login accepted by the server: {"yes" if capture.logins else "no"}', font=fonts['comment'], fill=COLORS['muted'])
		rules = ', '.join(sorted({e.text.split(' ')[0] for e in capture.events if e.lane == 'guard' and e.tone == 'fail' and e.text.startswith('CG')}))
		draw.text((x + 32, 446), f'Confirmed violations: {rules or "none"}', font=fonts['comment'], fill=COLORS['muted'])
		draw.text((x + 32, 490), f'{capture.status} · exit {capture.exit_code}', font=fonts['card'], fill=color)
	footer = 'pip install cookieguard-browser-use  ·  python -m cookieguard.browser_use.demo'
	draw.text(((WIDTH - draw.textlength(footer, font=fonts['code'])) / 2, 640), footer, font=fonts['code'], fill=COLORS['text'])
	return image


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


def compose(captures: list[Capture], out: Path, work: Path) -> dict:
	fonts = {'title': font(30), 'sub': font(22), 'caption': font(15), 'lane': font(15), 'mono': font(15, mono=True),
		'verdict': font(30), 'card': font(44), 'code': font(19, mono=True), 'comment': font(16)}
	frames_dir = work / 'composite'
	shutil.rmtree(frames_dir, ignore_errors=True)
	frames_dir.mkdir(parents=True)
	index = 0
	for capture in captures:
		card = title_card(capture, fonts)
		for _ in range(int(FPS * 1.6)):
			card.save(frames_dir / f'{index:05d}.png')
			index += 1
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
				decoded[position] = Image.open(__import__('io').BytesIO(capture.frames[position][1])).convert('RGB')
			render(capture, t, decoded[position], fonts, fast).save(frames_dir / f'{index:05d}.png')
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
		'-vf', 'fps=10,scale=1000:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];'
		'[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle', '-loop', '0', str(gif)], check=True)
	return {'frames': index, 'mp4': mp4, 'gif': gif}


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument('--out', default=str(HERE / 'docs'))
	parser.add_argument('--headed', action='store_true')
	parser.add_argument('--provider', choices=['scripted', 'anthropic'], default='scripted')
	parser.add_argument('--model', default='claude-opus-5-5', help='model id for --provider anthropic')
	args = parser.parse_args()
	global NOTE
	if args.provider == 'anthropic':
		if not os.environ.get('ANTHROPIC_API_KEY'):
			raise SystemExit('ANTHROPIC_API_KEY is not set.')
		NOTE = f'Real run · {args.model} drives the agent · long waits sped up'
	if not shutil.which('ffmpeg'):
		raise SystemExit('ffmpeg is required.')
	work = REPO / 'artifacts' / 'browser-use' / 'recording'
	work.mkdir(parents=True, exist_ok=True)
	captures = [asyncio.run(run_scenario(mode, headless=not args.headed, provider=args.provider, model=args.model))
		for mode in ('insecure', 'secure')]
	expected = {'insecure': ('FAIL', 1), 'secure': ('PASS', 0)}
	for capture in captures:
		if (capture.status, capture.exit_code) != expected[capture.mode] or capture.logins != 1:
			raise SystemExit(f'Unexpected result for {capture.mode}; recording withheld.')
	outputs = compose(captures, Path(args.out), work)
	provenance = {
		'recordedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'browser': captures[0].browser,
		'model': ('scripted stand-in (no AI provider); replies paced by %.1fs for viewing' % PACE_SECONDS
			if args.provider == 'scripted' else
			f'{args.model} via browser_use.ChatAnthropic (adaptive thinking; server-side fallback to claude-opus-4-8)'),
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
	(work / 'provenance.json').write_text(text)
	(Path(args.out) / 'demo-provenance.json').write_text(text)
	for path in (outputs['mp4'], outputs['gif']):
		print(f'{path}: {path.stat().st_size / 1e6:.1f} MB')
	print(f'Provenance: {Path(args.out) / "demo-provenance.json"}')
	return 0


if __name__ == '__main__':
	sys.exit(main())
