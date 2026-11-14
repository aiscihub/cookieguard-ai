export type UsageOptions = (
  | { package: 'cookieguard-ci'; integration: 'cli' | 'github-action' }
  | { package: '@aiscihub/cookieguard-playwright'; integration: 'playwright' }
  | { package: '@aiscihub/cookieguard-mcp'; integration: 'mcp' }
  | { package: '@aiscihub/cookieguard-core'; integration: 'core' }
) & {
  /** A version from the integration's trusted package manifest. */
  version: string;
  /** Enabled by default; false, COOKIEGUARD_USAGE_METRICS=0, or DO_NOT_TRACK=1 disables reporting. */
  enabled?: boolean | null;
};

/** Enqueue a minimal invocation event unless opted out. Never throws. */
export declare function reportUsage(options: UsageOptions): void;
/** Best-effort wait for queued events; timeout is capped at 1000 ms. Never rejects. */
export declare function flushUsage(timeoutMs?: number): Promise<void>;
