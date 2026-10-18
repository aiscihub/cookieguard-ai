import { normalizeCookie, parseSetCookie, evaluateCookiePolicy, formatJson, type Policy } from '@cookieguard/core';
import { createOnnxClassifier } from '@cookieguard/core/onnx';
import { scanUrl, runCli } from 'cookieguard-ci';
import { startCookieAudit, auditPage } from '@cookieguard/playwright';
import type { BrowserContext, Page } from 'playwright-core';

const policy: Policy = { authCookies: ['session_id'], failOn: 'high', allowedSameSite: ['strict', 'lax'] };
const observation = normalizeCookie({ name: 'session_id', secure: true, httpOnly: true }, { source: 'browser' });
const declared = parseSetCookie('session_id=synthetic; Secure; HttpOnly; SameSite=Lax', 'https://example.test');
formatJson(evaluateCookiePolicy([observation, declared], policy));
void scanUrl('http://localhost:3000');
void runCli(['--help']);
void createOnnxClassifier({ modelPath: 'model.onnx', metadataPath: 'model_meta.json' });
declare const context: BrowserContext;
declare const page: Page;
void startCookieAudit(context, { origins: ['http://localhost:3000'], policy }).evaluate();
void auditPage(page, { policy });
