import { PROTOCOL } from './constants';

export function tryParseResponse(
  bytes: Uint8Array,
): { method?: number; payload: unknown } | null {
  const text = new TextDecoder().decode(bytes).trim();
  try {
    return { payload: JSON.parse(text) };
  } catch {
    /* framed fallback */
  }
  if (bytes.length < 5) {
    return null;
  }
  const method = bytes[4];
  const body = new TextDecoder().decode(bytes.slice(5));
  try {
    return { method, payload: JSON.parse(body) };
  } catch {
    return { method, payload: body };
  }
}

export function isAuthOk(resp: Uint8Array | null): boolean {
  if (!resp || resp.length === 0) {
    return false;
  }
  const parsed = tryParseResponse(resp);
  if (!parsed) {
    return false;
  }
  if (typeof parsed.payload === 'object' && parsed.payload !== null) {
    const p = parsed.payload as Record<string, unknown>;
    if (p.result === 'ok' || p.code === 0 || p.status === 'success') {
      return true;
    }
    if (p.success === true) {
      return true;
    }
  }
  return parsed.method === PROTOCOL.METHOD_AUTH;
}

export function extractWifiIp(parsed: unknown): string | null {
  if (parsed === null || typeof parsed !== 'object') {
    return null;
  }
  const p = parsed as Record<string, unknown>;
  const ip = p.ip ?? p.IP ?? p.robot_ip;
  return typeof ip === 'string' && ip.length > 0 ? ip : null;
}
