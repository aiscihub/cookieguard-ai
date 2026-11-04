#!/usr/bin/env node
import { serveStdio, StdioServerTransport } from '@modelcontextprotocol/server/stdio';
import { createCookieGuardServer, VERSION } from '../src/index.js';
import { readConfig } from '../src/config.js';

const args = process.argv.slice(2);
try {
  if (args.length === 1 && args[0] === '--version') process.stdout.write(`${VERSION}\n`);
  else if (args.length === 1 && args[0] === '--help') {
    process.stdout.write('Usage: cookieguard-mcp --config /absolute/path/cookieguard.json\nLocal MCP over stdio. Configuration requires allowedOrigins; policy and timeoutMs are optional.\n');
  } else {
    if (args.length !== 2 || args[0] !== '--config') throw new Error();
    const config = await readConfig(args[1]);
    const handle = serveStdio(() => createCookieGuardServer(config), {
      transport: new StdioServerTransport(process.stdin, process.stdout, { maxBufferSize: 65536 }),
      onerror: () => { process.stderr.write('CookieGuard MCP transport error; details withheld.\n'); },
    });
    for (const signal of ['SIGINT', 'SIGTERM']) {
      process.once(signal, () => { void handle.close().finally(() => process.exit(0)); });
    }
  }
} catch {
  process.stderr.write('CookieGuard MCP could not start. Use --config with an absolute path to a valid configuration file.\n');
  process.exitCode = 2;
}
