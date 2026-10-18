import type { Observation } from '@aiscihub/cookieguard-core';
export interface ScanOptions { allowOrigins?: string[]; timeoutMs?: number }
export function validateTarget(target: string, allowOrigins?: string[]): URL;
export function scanUrl(target: string, options?: ScanOptions): Promise<{
  observations: Observation[]; target: string; mode: 'http'; complete: true;
}>;
export function runCli(args: string[], io?: { stdout: { write(text: string): unknown }; stderr: { write(text: string): unknown } }): Promise<0 | 1 | 2>;
