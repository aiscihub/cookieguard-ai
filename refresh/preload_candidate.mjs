import './common.mjs';
import { createCandidate } from './candidate.mjs';
if (!process.env.COOKIEGUARD_REFRESH_MODEL) throw new Error('candidate-path-required');
const classifier = await createCandidate(process.env.COOKIEGUARD_REFRESH_MODEL);
await classifier.classify({ name: 'refresh_synthetic_cookie', domain: 'localhost', path: '/', secure: true, httpOnly: true, sameSite: 'Lax' });
await classifier.dispose();
