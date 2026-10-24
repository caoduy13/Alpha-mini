import {PROTOCOL} from './constants';
const secretKey =
  /password|passphrase|passwd|pwd|token|salt|aes.*key|authorization|secret|credential/i;
const secrets = new Set<string>([PROTOCOL.AES_KEY]);
let frameSequence = 0;
export function rememberDiagnosticSecrets(...values: string[]): void {
  values.filter(Boolean).forEach(v => secrets.add(v));
  while (secrets.size > 128) {
    const oldest = Array.from(secrets).find(v => v !== PROTOCOL.AES_KEY);
    if (oldest) {
      secrets.delete(oldest);
    }
  }
}
export function redactDiagnostic(
  value: unknown,
  seen = new WeakSet<object>(),
): unknown {
  if (typeof value === 'string') {
    let text = value;
    for (const secret of secrets) {
      text = text.split(secret).join('[REDACTED]');
    }
    text = text.replace(/\b(?:[a-f\d]{2}[\s:]*){8,}/gi, '[REDACTED_HEX]');
    return text.replace(
      /(["']?(?:password|passphrase|passwd|pwd|token|salt|aes[_-]?key|authorization|secret)["']?\s*[:=]\s*)("(?:\\.|[^"\\])*"|'[^']*'|[^\s,;}]+)/gi,
      '$1[REDACTED]',
    );
  }
  if (!value || typeof value !== 'object') {
    return value;
  }
  if (seen.has(value)) {
    return '[CIRCULAR]';
  }
  seen.add(value);
  if (Array.isArray(value)) {
    return value.map(v => redactDiagnostic(v, seen));
  }
  const result: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    if (secretKey.test(key)) {
      result[key] = '[REDACTED]';
    } else if (/url|endpoint/i.test(key) && typeof item === 'string') {
      result[key] = redactDiagnostic(
        item.split(/[?#]/)[0].replace(/\/\/[^/@]+@/, '//[REDACTED]@'),
        seen,
      );
    } else {
      result[key] = redactDiagnostic(item, seen);
    }
  }
  return result;
}
export function bleErrorFields(error: unknown) {
  const e = error as Record<string, unknown> | null;
  return {
    message: e?.message ?? String(error),
    errorCode: e?.errorCode,
    androidErrorCode: e?.androidErrorCode,
    attErrorCode: e?.attErrorCode,
    reason: e?.reason,
  };
}
export function maskedDeviceId(id: string): string {
  return `device:...${id.slice(-4)}`;
}
function stringEnd(text: string, start: number): number {
  for (let i = start + 1; i < text.length; i++) {
    if (text[i] === '\\') {
      i++;
    } else if (text[i] === '"') {
      return i + 1;
    }
  }
  return text.length;
}
function valueEnd(text: string, start: number): number {
  if (text[start] === '"') {
    return stringEnd(text, start);
  }
  let depth = 0;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      i = stringEnd(text, i) - 1;
    } else if (ch === '{' || ch === '[') {
      depth++;
    } else if (ch === '}' || ch === ']') {
      if (depth === 0) {
        return i;
      }
      if (--depth === 0) {
        return i + 1;
      }
    } else if (ch === ',' && depth === 0) {
      return i;
    }
  }
  return text.length;
}
/** Keep wire offsets/length; mask protected bytes with 0x2a, never reserialize JSON. */
export function describeDiagnosticFrame(bytes: Uint8Array) {
  const safe = new Uint8Array(bytes);
  const size = bytes.length;
  const length =
    size >= 5
      ? new DataView(
          bytes.buffer,
          bytes.byteOffset,
          bytes.byteLength,
        ).getUint32(0)
      : -1;
  const headerSize = length === size - 4 ? 5 : 0;
  let format = 'opaque';
  try {
    const body = new TextDecoder('utf-8', {fatal: true}).decode(
      bytes.slice(headerSize),
    );
    if (new TextEncoder().encode(body).length !== bytes.length - headerSize) {
      throw new Error('decoded payload offsets are not byte-exact');
    }
    const parsed: unknown = JSON.parse(body);
    if (!parsed || typeof parsed !== 'object') {
      throw new Error('not structured JSON');
    }
    format = headerSize ? 'framed-json' : 'json';
    const keys = /"(?:\\.|[^"\\])*"\s*:/g;
    let match: RegExpExecArray | null;
    while ((match = keys.exec(body))) {
      const key = JSON.parse(
        match[0].slice(0, match[0].lastIndexOf(':')).trim(),
      ) as string;
      if (!secretKey.test(key)) {
        continue;
      }
      let start = keys.lastIndex;
      while (start < body.length && /\s/.test(body[start])) {
        start++;
      }
      const end = valueEnd(body, start);
      try {
        const v: unknown = JSON.parse(body.slice(start, end));
        if (typeof v === 'string') {
          rememberDiagnosticSecrets(v);
        }
      } catch {
        /* still mask */
      }
      safe.fill(
        0x2a,
        headerSize + new TextEncoder().encode(body.slice(0, start)).length,
        headerSize + new TextEncoder().encode(body.slice(0, end)).length,
      );
    }
    for (const secret of secrets) {
      for (const encoded of [
        new TextEncoder().encode(secret),
        new TextEncoder().encode(JSON.stringify(secret).slice(1, -1)),
      ]) {
        for (let i = headerSize; i <= size - encoded.length; i++) {
          if (encoded.length && encoded.every((b, j) => bytes[i + j] === b)) {
            safe.fill(0x2a, i, i + encoded.length);
          }
        }
      }
    }
  } catch {
    safe.fill(0x2a, headerSize);
  }
  const hex = (data: Uint8Array) =>
    Array.from(data, b => b.toString(16).padStart(2, '0')).join('');
  return {
    byteLength: size,
    format,
    method: headerSize ? bytes[4] : undefined,
    headerHex: hex(safe.slice(0, headerSize)),
    rawHex: hex(safe),
    redactedByte: '2a',
  };
}
export function bleDiag(
  event: string,
  fields: Record<string, unknown> = {},
  frame?: Uint8Array,
): void {
  try {
    const frameId = frame ? ++frameSequence : undefined;
    const safeFrame = frame ? describeDiagnosticFrame(frame) : undefined;
    const {rawHex, ...frameInfo} = safeFrame ?? {rawHex: ''};
    console.info(
      '[BLE-DIAG]',
      JSON.stringify({
        event,
        at: Date.now(),
        ...(redactDiagnostic(fields) as object),
        ...(frame ? {frameId, frame: frameInfo} : {}),
      }),
    );
    if (frame) {
      for (let offset = 0; offset < rawHex.length; offset += 384) {
        console.info(
          '[BLE-DIAG]',
          JSON.stringify({
            event: 'frame-bytes',
            frameId,
            offsetBytes: offset / 2,
            hex: rawHex.slice(offset, offset + 384),
            last: offset + 384 >= rawHex.length,
          }),
        );
      }
    }
  } catch {
    /* Diagnostics never change BLE outcomes. */
  }
}
