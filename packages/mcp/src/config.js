import { open } from 'node:fs/promises';
import { isAbsolute } from 'node:path';
import { AuditError, validatePolicy } from '@aiscihub/cookieguard-core';
import { validateTarget } from 'cookieguard-ci';

export function validateConfig(input) {
  try {
    if (!input || typeof input !== 'object' || Array.isArray(input)
      || Object.keys(input).some(key => !['allowedOrigins', 'policy', 'timeoutMs'].includes(key))) throw new Error();
    if (!Array.isArray(input.allowedOrigins) || !input.allowedOrigins.length || input.allowedOrigins.length > 20) throw new Error();
    const allowedOrigins = [...new Set(input.allowedOrigins.map(origin => {
      if (typeof origin !== 'string') throw new Error();
      const url = validateTarget(origin, [origin]);
      if (url.pathname !== '/') throw new Error();
      return url.origin;
    }))];
    const timeoutMs = input.timeoutMs ?? 10000;
    if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 10000) throw new Error();
    // Copy caller-owned arrays/objects so subsequent mutations cannot change policy.
    return structuredClone({ allowedOrigins, policy: validatePolicy(input.policy), timeoutMs });
  } catch { throw new AuditError('CONFIG'); }
}

export async function readConfig(path) {
  let file;
  try {
    if (typeof path !== 'string' || !isAbsolute(path)) throw new Error();
    file = await open(path, 'r');
    const info = await file.stat();
    if (!info.isFile() || info.size > 65536) throw new Error();
    // Limit the read as well as stat: the file can change between these operations.
    const buffer = Buffer.alloc(65537);
    let length = 0;
    while (length < buffer.length) {
      const { bytesRead } = await file.read(buffer, length, buffer.length - length, null);
      if (!bytesRead) break;
      length += bytesRead;
    }
    if (length > 65536) throw new Error();
    return validateConfig(JSON.parse(buffer.subarray(0, length).toString('utf8')));
  } catch { throw new AuditError('CONFIG'); }
  finally { await file?.close(); }
}
