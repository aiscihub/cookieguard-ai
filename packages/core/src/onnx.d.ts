import type { CookieInput, Triage } from './index.js';
export interface OnnxClassifier {
  readonly mode: 'onnx'; classify(cookie: CookieInput): Promise<Triage>; dispose(): Promise<void>;
}
/** Requires separately installed onnxruntime-node and the existing model/metadata files. */
export function createOnnxClassifier(options: { modelPath: string; metadataPath: string }): Promise<OnnxClassifier>;
