import type { McpServer } from '@modelcontextprotocol/server';
import type { Policy } from '@aiscihub/cookieguard-core';

export interface CookieGuardMcpOptions {
  /** Required exact HTTP(S) origins, including scheme and port; at most 20. */
  allowedOrigins: string[];
  /** Trusted startup policy; cannot be overridden through tool arguments. */
  policy?: Policy;
  /** Total scan timeout, 100–10000 milliseconds. Default: 10000. */
  timeoutMs?: number;
  /**
   * Absolute directory of sanitized CookieGuard JSON reports written by your own
   * tests. Enables cookieguard_audit {"evidenceFile"}. Resolved once at startup.
   */
  evidenceDir?: string;
}
export const VERSION: string;
/** Creates an unconnected MCP server with an independent configuration snapshot. */
export function createCookieGuardServer(options: CookieGuardMcpOptions): McpServer;
