/* eslint-disable no-bitwise -- byte-level wire codec */
import { Buffer } from 'buffer';

/**
 * Alpha Mini BLE wire codec (see docs/ble-protocol.md §2, §3, §13).
 *
 * GATT value = chunk(<=16 bytes) of logical frame + groupId:uint16BE + fragmentNo:uint16BE
 * Logical frame = FB BF 01 L:uint16BE CodeMaoMessage 01 ED, with L = payload + 6.
 */

export const FRAME_MAGIC_0 = 0xfb;
export const FRAME_MAGIC_1 = 0xbf;
export const FRAME_VERSION = 0x01;
const FRAME_FIXED = 0x01;
const FRAME_END = 0xed;
const FRAME_OVERHEAD = 7;
export const FRAGMENT_DATA_SIZE = 16;
const FRAGMENT_TRAILER_SIZE = 4;

export const CMD = {
  HANDSHAKE: 0,
  HANDSHAKE_RESPONSE: 1000,
  BIND_OR_SWITCH_WIFI: 32,
  BIND_OR_SWITCH_WIFI_RESPONSE: 1032,
} as const;

export const MSG_TYPE = {
  RESPONSE_COMPLETE: 0,
  RESPONSE_STICKY: 1,
  REQUEST: 2,
} as const;

/** BindOrSwitchWifiRequest.versionCode sent by the vendor SDK. */
export const WIFI_REQUEST_VERSION_CODE = 168;
/** MessageHeader.versionCode used by the probe handshake and the SDK request builder. */
export const HEADER_VERSION_CODE = 1;

export class BleCodecError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'BleCodecError';
    this.code = code;
  }
}

export function utf8Encode(text: string): Uint8Array {
  return new Uint8Array(Buffer.from(text, 'utf8'));
}

export function utf8Decode(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString('utf8');
}

// ---------------------------------------------------------------------------
// Protobuf (proto3) primitives: only what the schemas in §3 need.

const WIRE_VARINT = 0;
const WIRE_FIXED64 = 1;
const WIRE_LEN = 2;
const WIRE_FIXED32 = 5;

function encodeVarint(value: number): number[] {
  if (!Number.isInteger(value) || value < 0 || value > 0xffffffff) {
    throw new BleCodecError('bad-varint', `cannot encode varint ${value}`);
  }
  const out: number[] = [];
  let v = value;
  while (v > 0x7f) {
    out.push((v % 0x80) | 0x80);
    v = Math.floor(v / 0x80);
  }
  out.push(v);
  return out;
}

function tag(field: number, wire: number): number[] {
  return encodeVarint(field * 8 + wire);
}

function encodeIntField(field: number, value: number): number[] {
  return value === 0 ? [] : [...tag(field, WIRE_VARINT), ...encodeVarint(value)];
}

function encodeBytesField(field: number, value: Uint8Array): number[] {
  return value.length === 0
    ? []
    : [...tag(field, WIRE_LEN), ...encodeVarint(value.length), ...value];
}

function encodeStringField(field: number, value: string): number[] {
  return encodeBytesField(field, utf8Encode(value));
}

export type ProtoField = {
  field: number;
  wire: number;
  /** Offset of the tag byte. */
  start: number;
  /** Offset of the value (after tag and, for LEN, after the length prefix). */
  valueStart: number;
  /** Offset just past the value. */
  end: number;
  /** Varint value truncated to signed int32 (proto int32/bool/enum). */
  int: number;
};

function readVarint(buf: Uint8Array, offset: number): { value: number; next: number } {
  let low = 0;
  let pos = offset;
  for (let i = 0; i < 10; i++) {
    if (pos >= buf.length) {
      throw new BleCodecError('truncated-varint', `varint truncated at ${offset}`);
    }
    const b = buf[pos++];
    if (i < 5) {
      // Low 32 bits only: int32 negatives arrive as 10-byte two's complement varints.
      low |= (b & 0x7f) << (7 * i);
    }
    if ((b & 0x80) === 0) {
      return { value: low | 0, next: pos };
    }
  }
  throw new BleCodecError('bad-varint', `varint longer than 10 bytes at ${offset}`);
}

export function readProtoFields(buf: Uint8Array): ProtoField[] {
  const fields: ProtoField[] = [];
  let pos = 0;
  while (pos < buf.length) {
    const start = pos;
    const key = readVarint(buf, pos);
    pos = key.next;
    const field = key.value >>> 3;
    const wire = key.value & 7;
    if (field === 0) {
      throw new BleCodecError('bad-tag', `field number 0 at ${start}`);
    }
    let valueStart = pos;
    let int = 0;
    if (wire === WIRE_VARINT) {
      const v = readVarint(buf, pos);
      int = v.value;
      pos = v.next;
    } else if (wire === WIRE_LEN) {
      const len = readVarint(buf, pos);
      valueStart = len.next;
      pos = len.next + (len.value >>> 0);
    } else if (wire === WIRE_FIXED64) {
      pos += 8;
    } else if (wire === WIRE_FIXED32) {
      pos += 4;
    } else {
      throw new BleCodecError('bad-wire-type', `wire type ${wire} at ${start}`);
    }
    if (pos > buf.length) {
      throw new BleCodecError('truncated-field', `field ${field} overruns buffer`);
    }
    fields.push({ field, wire, start, valueStart, end: pos, int });
  }
  return fields;
}

function lastField(fields: ProtoField[], field: number, wire: number): ProtoField | undefined {
  // proto3: the last occurrence of a scalar wins.
  for (let i = fields.length - 1; i >= 0; i--) {
    if (fields[i].field === field && fields[i].wire === wire) {
      return fields[i];
    }
  }
  return undefined;
}

function intOf(fields: ProtoField[], field: number): number {
  return lastField(fields, field, WIRE_VARINT)?.int ?? 0;
}

function bytesOf(buf: Uint8Array, fields: ProtoField[], field: number): Uint8Array {
  const f = lastField(fields, field, WIRE_LEN);
  return f ? buf.slice(f.valueStart, f.end) : new Uint8Array(0);
}

function stringOf(buf: Uint8Array, fields: ProtoField[], field: number): string {
  return utf8Decode(bytesOf(buf, fields, field));
}

// ---------------------------------------------------------------------------
// Schemas (§3): CodeMaoMessage / MessageHeader / handshake / BindOrSwitchWifi.

export type MessageHeader = {
  commandId: number;
  sendSerial: number;
  responseSerial: number;
  versionCode: number;
  msgType: number;
  resultCode: number;
};

export type MiniMessage = { header: MessageHeader; body: Uint8Array };

export function encodeHeader(h: Partial<MessageHeader>): Uint8Array {
  return new Uint8Array([
    ...encodeIntField(1, h.commandId ?? 0),
    ...encodeIntField(2, h.sendSerial ?? 0),
    ...encodeIntField(3, h.responseSerial ?? 0),
    ...encodeIntField(4, h.versionCode ?? 0),
    ...encodeIntField(5, h.msgType ?? 0),
    ...encodeIntField(6, h.resultCode ?? 0),
  ]);
}

export function encodeMessage(header: Partial<MessageHeader>, body: Uint8Array): Uint8Array {
  // The header is always present on the wire, even when every field is default.
  const h = encodeHeader(header);
  return new Uint8Array([
    ...tag(1, WIRE_LEN),
    ...encodeVarint(h.length),
    ...h,
    ...encodeBytesField(2, body),
  ]);
}

export function decodeMessage(payload: Uint8Array): MiniMessage {
  const fields = readProtoFields(payload);
  const headerBytes = bytesOf(payload, fields, 1);
  const hf = readProtoFields(headerBytes);
  return {
    header: {
      commandId: intOf(hf, 1),
      sendSerial: intOf(hf, 2),
      responseSerial: intOf(hf, 3),
      versionCode: intOf(hf, 4),
      msgType: intOf(hf, 5),
      resultCode: intOf(hf, 6),
    },
    body: bytesOf(payload, fields, 2),
  };
}

export type HandshakeResponse = {
  isSuccess: boolean;
  /** bool in the schema; not an error code. */
  resultCode: boolean;
  sysLan: string;
  sysCountry: string;
  robotSoftVersionName: string;
  btInterfaceVersion: number;
  androidFirmwareVersion: string;
  errorCode: number;
  sessionId: string;
  versionInfo: string;
};

export function decodeHandshakeResponse(body: Uint8Array): HandshakeResponse {
  const f = readProtoFields(body);
  return {
    isSuccess: intOf(f, 1) !== 0,
    resultCode: intOf(f, 2) !== 0,
    sysLan: stringOf(body, f, 3),
    sysCountry: stringOf(body, f, 4),
    robotSoftVersionName: stringOf(body, f, 5),
    btInterfaceVersion: intOf(f, 6),
    androidFirmwareVersion: stringOf(body, f, 7),
    errorCode: intOf(f, 8),
    sessionId: stringOf(body, f, 9),
    versionInfo: stringOf(body, f, 10),
  };
}

/** Field numbers of secret values, used by diagnostics to mask by offset. */
export const SECRET_FIELDS = {
  handshakeRequest: [6, 7],
  handshakeResponse: [9],
} as const;

export function encodeWifiRequest(data: string, versionCode = WIFI_REQUEST_VERSION_CODE): Uint8Array {
  return new Uint8Array([...encodeStringField(1, data), ...encodeIntField(2, versionCode)]);
}

export function decodeWifiRequest(body: Uint8Array): { data: string; versionCode: number } {
  const f = readProtoFields(body);
  return { data: stringOf(body, f, 1), versionCode: intOf(f, 2) };
}

export function decodeWifiResponse(body: Uint8Array): { data: string } {
  const f = readProtoFields(body);
  return { data: stringOf(body, f, 1) };
}

// ---------------------------------------------------------------------------
// Logical frame.

export function packFrame(payload: Uint8Array): Uint8Array {
  const length = payload.length + 6;
  if (length > 0xffff) {
    throw new BleCodecError('frame-too-large', `payload of ${payload.length} bytes`);
  }
  const out = new Uint8Array(payload.length + FRAME_OVERHEAD);
  out.set([FRAME_MAGIC_0, FRAME_MAGIC_1, FRAME_VERSION, length >> 8, length & 0xff]);
  out.set(payload, 5);
  out[out.length - 2] = FRAME_FIXED;
  out[out.length - 1] = FRAME_END;
  return out;
}

/** Total logical frame length declared by the first 5 bytes, or -1 if not a frame start. */
export function declaredFrameLength(bytes: Uint8Array): number {
  if (bytes.length < 5 || bytes[0] !== FRAME_MAGIC_0 || bytes[1] !== FRAME_MAGIC_1) {
    return -1;
  }
  return ((bytes[3] << 8) | bytes[4]) + 1;
}

export function unpackFrame(frame: Uint8Array): Uint8Array {
  if (frame.length < FRAME_OVERHEAD) {
    throw new BleCodecError('short-frame', `frame of ${frame.length} bytes`);
  }
  if (frame[0] !== FRAME_MAGIC_0 || frame[1] !== FRAME_MAGIC_1) {
    throw new BleCodecError('bad-magic', 'frame does not start with FB BF');
  }
  const expected = declaredFrameLength(frame);
  if (expected !== frame.length) {
    throw new BleCodecError('bad-length', `declared ${expected} bytes, got ${frame.length}`);
  }
  if (frame[frame.length - 1] !== FRAME_END) {
    throw new BleCodecError('bad-end', 'frame does not end with ED');
  }
  return frame.slice(5, frame.length - 2);
}

// ---------------------------------------------------------------------------
// GATT fragmentation.

export function fragmentFrame(frame: Uint8Array, groupId: number): Uint8Array[] {
  if (!Number.isInteger(groupId) || groupId < 0 || groupId > 0xffff) {
    throw new BleCodecError('bad-group', `groupId ${groupId}`);
  }
  const count = Math.ceil(frame.length / FRAGMENT_DATA_SIZE);
  if (count > 0xffff) {
    throw new BleCodecError('frame-too-large', `${count} fragments`);
  }
  const out: Uint8Array[] = [];
  for (let i = 0; i < count; i++) {
    const chunk = frame.slice(i * FRAGMENT_DATA_SIZE, (i + 1) * FRAGMENT_DATA_SIZE);
    const value = new Uint8Array(chunk.length + FRAGMENT_TRAILER_SIZE);
    value.set(chunk);
    const n = i + 1;
    value.set([groupId >> 8, groupId & 0xff, n >> 8, n & 0xff], chunk.length);
    out.push(value);
  }
  return out;
}

export function parseFragment(value: Uint8Array): {
  data: Uint8Array;
  groupId: number;
  fragmentNo: number;
} {
  if (value.length <= FRAGMENT_TRAILER_SIZE) {
    throw new BleCodecError('short-fragment', `GATT value of ${value.length} bytes`);
  }
  const t = value.length - FRAGMENT_TRAILER_SIZE;
  return {
    data: value.slice(0, t),
    groupId: (value[t] << 8) | value[t + 1],
    fragmentNo: (value[t + 2] << 8) | value[t + 3],
  };
}

export function randomGroupId(): number {
  return 1 + Math.floor(Math.random() * 0xfffe);
}

export type ReassemblyResult =
  | { status: 'complete'; frame: Uint8Array; groupId: number; fragments: number }
  | {
      status: 'pending';
      groupId: number;
      fragmentNo: number;
      receivedBytes: number;
      expectedBytes: number;
      /** Set when a new frame started before the previous one completed. */
      dropped?: { groupId: number; receivedBytes: number; expectedBytes: number };
    }
  | { status: 'duplicate'; groupId: number; fragmentNo: number }
  | { status: 'error'; code: string; message: string };

/**
 * Rebuilds logical frames from indications. Never blocks: every input returns a result, and
 * any inconsistency resets state with an explicit error (callers time out separately).
 */
export class FrameReassembler {
  private groupId = -1;
  private lastFragmentNo = 0;
  private expected = 0;
  private parts: Uint8Array[] = [];
  private received = 0;

  reset(): void {
    this.groupId = -1;
    this.lastFragmentNo = 0;
    this.expected = 0;
    this.parts = [];
    this.received = 0;
  }

  get pending(): boolean {
    return this.groupId >= 0;
  }

  push(value: Uint8Array): ReassemblyResult {
    let frag: ReturnType<typeof parseFragment>;
    try {
      frag = parseFragment(value);
    } catch (e) {
      return this.fail(e);
    }
    if (this.groupId >= 0 && frag.groupId === this.groupId) {
      if (frag.fragmentNo === this.lastFragmentNo) {
        return { status: 'duplicate', groupId: frag.groupId, fragmentNo: frag.fragmentNo };
      }
      if (frag.fragmentNo !== this.lastFragmentNo + 1) {
        const message = `group ${frag.groupId}: expected fragment ${this.lastFragmentNo + 1}, got ${frag.fragmentNo}`;
        this.reset();
        return { status: 'error', code: 'fragment-out-of-order', message };
      }
      return this.append(frag.data, frag.fragmentNo);
    }

    let dropped: { groupId: number; receivedBytes: number; expectedBytes: number } | undefined;
    if (this.groupId >= 0) {
      dropped = { groupId: this.groupId, receivedBytes: this.received, expectedBytes: this.expected };
      this.reset();
    }
    if (frag.fragmentNo !== 1) {
      return {
        status: 'error',
        code: 'missing-first-fragment',
        message: `group ${frag.groupId} started at fragment ${frag.fragmentNo}`,
      };
    }
    const expected = declaredFrameLength(frag.data);
    if (expected < 0) {
      return { status: 'error', code: 'bad-magic', message: `group ${frag.groupId} does not start with FB BF` };
    }
    if (expected < FRAME_OVERHEAD) {
      return { status: 'error', code: 'bad-length', message: `declared frame length ${expected}` };
    }
    this.groupId = frag.groupId;
    this.expected = expected;
    const result = this.append(frag.data, 1);
    return result.status === 'pending' && dropped ? { ...result, dropped } : result;
  }

  private append(data: Uint8Array, fragmentNo: number): ReassemblyResult {
    this.parts.push(data);
    this.received += data.length;
    this.lastFragmentNo = fragmentNo;
    const groupId = this.groupId;
    if (this.received < this.expected) {
      return {
        status: 'pending',
        groupId,
        fragmentNo,
        receivedBytes: this.received,
        expectedBytes: this.expected,
      };
    }
    if (this.received > this.expected) {
      const message = `group ${groupId}: ${this.received} bytes exceed declared ${this.expected}`;
      this.reset();
      return { status: 'error', code: 'frame-overflow', message };
    }
    const frame = new Uint8Array(this.received);
    let pos = 0;
    for (const p of this.parts) {
      frame.set(p, pos);
      pos += p.length;
    }
    const fragments = this.lastFragmentNo;
    this.reset();
    try {
      unpackFrame(frame);
    } catch (e) {
      return this.fail(e);
    }
    return { status: 'complete', frame, groupId, fragments };
  }

  private fail(e: unknown): ReassemblyResult {
    this.reset();
    return e instanceof BleCodecError
      ? { status: 'error', code: e.code, message: e.message }
      : { status: 'error', code: 'unknown', message: String(e) };
  }
}

// ---------------------------------------------------------------------------
// Request builders.

/** Empty BluetoothHandShakeRequest, exactly the probe accepted by firmware v2.2.5.917 (§6, §9). */
export function buildHandshakeFrame(sendSerial: number): Uint8Array {
  return packFrame(
    encodeMessage(
      { commandId: CMD.HANDSHAKE, sendSerial, versionCode: HEADER_VERSION_CODE, msgType: MSG_TYPE.REQUEST },
      new Uint8Array(0),
    ),
  );
}

/** Command 32 as built by the SDK request builder: no msgType, responseSerial 0 (§13.2). */
export function buildWifiCommandFrame(data: string, sendSerial: number): Uint8Array {
  return packFrame(
    encodeMessage(
      { commandId: CMD.BIND_OR_SWITCH_WIFI, sendSerial, versionCode: HEADER_VERSION_CODE },
      encodeWifiRequest(data),
    ),
  );
}

export function decodeFrame(frame: Uint8Array): MiniMessage {
  return decodeMessage(unpackFrame(frame));
}
