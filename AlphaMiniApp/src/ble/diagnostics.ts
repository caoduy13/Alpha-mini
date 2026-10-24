import {
  CMD,
  SECRET_FIELDS,
  decodeMessage,
  decodeWifiRequest,
  decodeWifiResponse,
  readProtoFields,
  unpackFrame,
  utf8Encode,
} from './codec';
import { parseWifiNotification } from './wifi';

const secretKey =
  /password|passphrase|passwd|pwd|token|salt|aes.*key|authorization|secret|credential|session/i;
const secrets = new Set<string>();
let frameSequence = 0;
export function rememberDiagnosticSecrets(...values: string[]): void {
  values.filter(Boolean).forEach(v => secrets.add(v));
  while (secrets.size > 128) {
    const oldest = secrets.values().next().value;
    if (oldest === undefined) {
      break;
    }
    secrets.delete(oldest);
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
      /(["']?(?:password|passphrase|passwd|pwd|token|salt|aes[_-]?key|authorization|secret|session[_-]?id)["']?\s*[:=]\s*)("(?:\\.|[^"\\])*"|'[^']*'|[^\s,;}]+)/gi,
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

const FRAME_PREFIX = 5;
const REDACTED = 0x2a;

type FrameSummary = {
  commandId?: number;
  sendSerial?: number;
  responseSerial?: number;
  msgType?: number;
  /** "co"/"ec"/"cd"/networkCount from command 32/1032 JSON; other JSON values are masked. */
  wifi?: Record<string, unknown>;
};

/** Masks [start, end) of the body (offsets relative to the frame). */
function maskBodyFields(
  safe: Uint8Array,
  body: Uint8Array,
  bodyOffset: number,
  fieldNumbers: readonly number[],
) {
  for (const f of readProtoFields(body)) {
    if (fieldNumbers.includes(f.field)) {
      safe.fill(REDACTED, bodyOffset + f.valueStart, bodyOffset + f.end);
    }
  }
}

function wifiSummary(data: string): Record<string, unknown> {
  const n = parseWifiNotification(data);
  if (!n) {
    return { parsed: false };
  }
  const { co, ec, cd, networkCount } = n;
  return { co, ec, cd, networkCount };
}

/**
 * Logical-frame view for logs: keeps byte offsets and header, masks every secret by protobuf
 * offset (session ids, the whole Wi-Fi JSON string) and fails closed on anything unparseable.
 */
export function describeDiagnosticFrame(bytes: Uint8Array) {
  const safe = new Uint8Array(bytes);
  const size = bytes.length;
  let format = 'opaque';
  const summary: FrameSummary = {};
  try {
    const payload = unpackFrame(bytes);
    const fields = readProtoFields(payload);
    const bodyField = fields.filter(f => f.field === 2 && f.wire === 2).at(-1);
    const { header, body } = decodeMessage(payload);
    const bodyOffset = FRAME_PREFIX + (bodyField?.valueStart ?? payload.length);
    summary.commandId = header.commandId;
    summary.sendSerial = header.sendSerial;
    summary.responseSerial = header.responseSerial;
    summary.msgType = header.msgType;
    if (header.commandId === CMD.HANDSHAKE) {
      maskBodyFields(safe, body, bodyOffset, SECRET_FIELDS.handshakeRequest);
    } else if (header.commandId === CMD.HANDSHAKE_RESPONSE) {
      maskBodyFields(safe, body, bodyOffset, SECRET_FIELDS.handshakeResponse);
    } else if (header.commandId === CMD.BIND_OR_SWITCH_WIFI) {
      summary.wifi = wifiSummary(decodeWifiRequest(body).data);
      maskBodyFields(safe, body, bodyOffset, [1]);
    } else if (header.commandId === CMD.BIND_OR_SWITCH_WIFI_RESPONSE) {
      summary.wifi = wifiSummary(decodeWifiResponse(body).data);
      maskBodyFields(safe, body, bodyOffset, [1]);
    } else {
      safe.fill(REDACTED, bodyOffset, FRAME_PREFIX + payload.length);
    }
    format = 'mini-ble';
  } catch {
    safe.fill(REDACTED, Math.min(FRAME_PREFIX, size));
  }
  // Defense in depth: known secrets anywhere in the bytes.
  for (const secret of secrets) {
    const encoded = utf8Encode(secret);
    for (let i = 0; encoded.length && i <= size - encoded.length; i++) {
      if (encoded.every((b, j) => bytes[i + j] === b)) {
        safe.fill(REDACTED, i, i + encoded.length);
      }
    }
  }
  const hex = (data: Uint8Array) =>
    Array.from(data, b => b.toString(16).padStart(2, '0')).join('');
  return {
    byteLength: size,
    format,
    ...summary,
    headerHex: hex(safe.slice(0, Math.min(FRAME_PREFIX, size))),
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
