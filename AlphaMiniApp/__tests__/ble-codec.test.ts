import { Buffer } from 'buffer';
import {
  CMD,
  FrameReassembler,
  buildHandshakeFrame,
  buildWifiCommandFrame,
  decodeFrame,
  decodeHandshakeResponse,
  decodeWifiRequest,
  encodeMessage,
  fragmentFrame,
  packFrame,
  unpackFrame,
  utf8Encode,
} from '../src/ble/codec';
import {
  parseWifiNotification,
  quitNetworkConfigJson,
  startNetworkConfigJson,
  wifiConfigJson,
} from '../src/ble/wifi';
import sdkGolden from './fixtures/ble-golden-sdk.json';
import capture from './fixtures/ble-capture-handshake-redacted.json';

const hex = (u: Uint8Array) =>
  Array.from(u, b => b.toString(16).padStart(2, '0')).join('').toUpperCase();
const bytes = (h: string) => new Uint8Array(Buffer.from(h, 'hex'));

type WifiVector = {
  data: string;
  sendSerial: number;
  frameHex: string;
  groupId: number;
  fragmentsHex: string[];
};

const wifiVectors: Array<[string, WifiVector]> = [
  ['startNetworkConfig', sdkGolden.startNetworkConfig],
  ['wifiConfig', sdkGolden.wifiConfig],
  ['wifiConfigOpenUnicode', sdkGolden.wifiConfigOpenUnicode],
  ['exitNetworkConfig', sdkGolden.exitNetworkConfig],
];

describe('SDK offline golden vectors (synthetic, fake Wi-Fi)', () => {
  test('handshake frame is the 19-byte probe accepted by the robot', () => {
    const frame = buildHandshakeFrame(1);
    expect(hex(frame)).toBe(sdkGolden.handshakeRequest.frameHex);
    const values = fragmentFrame(frame, sdkGolden.handshakeRequest.groupId);
    expect(values.map(hex)).toEqual(sdkGolden.handshakeRequest.fragmentsHex);
    expect(hex(values[0])).toBe('FBBF01000E0A0610012001280201ED00010001');
  });

  test.each(wifiVectors)('%s encodes byte-for-byte like the SDK', (_name, v) => {
    const frame = buildWifiCommandFrame(v.data, v.sendSerial);
    expect(hex(frame)).toBe(v.frameHex);
    expect(fragmentFrame(frame, v.groupId).map(hex)).toEqual(v.fragmentsHex);
    const msg = decodeFrame(frame);
    expect(msg.header).toMatchObject({
      commandId: CMD.BIND_OR_SWITCH_WIFI,
      sendSerial: v.sendSerial,
      responseSerial: 0,
      versionCode: 1,
      msgType: 0,
    });
    expect(decodeWifiRequest(msg.body)).toEqual({ data: v.data, versionCode: 168 });
  });

  test('JSON builders reproduce the SDK data strings', () => {
    expect(startNetworkConfigJson()).toBe(sdkGolden.startNetworkConfig.data);
    expect(quitNetworkConfigJson()).toBe(sdkGolden.exitNetworkConfig.data);
    expect(wifiConfigJson({ ssid: 'Lab-WiFi-Test', password: 'fake-pass-1234' })).toBe(
      sdkGolden.wifiConfig.data,
    );
    expect(wifiConfigJson({ ssid: 'Open Lab É', password: '' })).toBe(
      sdkGolden.wifiConfigOpenUnicode.data,
    );
  });

  test('passwords with JSON/HTML special characters survive a JSON round trip', () => {
    const password = ['fa"ke', '\\', "<=&>'", String.fromCharCode(0x2028)].join('');
    const data = wifiConfigJson({ ssid: 'x', password });
    expect(JSON.parse(data).p).toBe(password);
    const frame = buildWifiCommandFrame(data, 3);
    expect(decodeWifiRequest(decodeFrame(frame).body).data).toBe(data);
  });
});

describe('real robot handshake capture (sessionId replaced by fake value)', () => {
  test.each(capture.runs)('$name reassembles from 5 indications and decodes', run => {
    const r = new FrameReassembler();
    const results = run.fragmentsHex.map(f => r.push(bytes(f)));
    expect(results.slice(0, 4).map(x => x.status)).toEqual(['pending', 'pending', 'pending', 'pending']);
    const last = results[4];
    if (last.status !== 'complete') {
      throw new Error(`expected complete, got ${JSON.stringify(last)}`);
    }
    expect(last.groupId).toBe(run.groupId);
    expect(last.fragments).toBe(5);
    expect(last.frame.length).toBe(77);
    const msg = decodeFrame(last.frame);
    const { body: expectedBody, ...expectedHeader } = capture.expected;
    expect(msg.header).toEqual(expectedHeader);
    const body = decodeHandshakeResponse(msg.body);
    expect(body).toMatchObject(expectedBody);
    expect(body.sessionId).toBe(capture.fakeSessionId);
    expect(r.pending).toBe(false);
  });
});

describe('reassembly failures are explicit and never wedge the parser', () => {
  const values = capture.runs[0].fragmentsHex.map(bytes);
  const good = capture.runs[1].fragmentsHex.map(bytes);

  function feedAll(r: FrameReassembler, list: Uint8Array[]) {
    return list.map(v => r.push(v));
  }

  test('missing middle fragment reports out-of-order and recovers for the next frame', () => {
    const r = new FrameReassembler();
    const res = feedAll(r, [values[0], values[1], values[3], values[4]]);
    expect(res[2]).toMatchObject({ status: 'error', code: 'fragment-out-of-order' });
    expect(res[3]).toMatchObject({ status: 'error', code: 'missing-first-fragment' });
    expect(feedAll(r, good).at(-1)?.status).toBe('complete');
  });

  test('swapped fragments report out-of-order', () => {
    const r = new FrameReassembler();
    const res = feedAll(r, [values[0], values[2], values[1]]);
    expect(res[1]).toMatchObject({ status: 'error', code: 'fragment-out-of-order' });
    expect(r.pending).toBe(false);
  });

  test('duplicate fragment is ignored like the robot PacketData', () => {
    const r = new FrameReassembler();
    const res = feedAll(r, [values[0], values[1], values[1], values[2], values[3], values[4]]);
    expect(res[2].status).toBe('duplicate');
    expect(res.at(-1)?.status).toBe('complete');
  });

  test('a new group while incomplete drops the old frame visibly', () => {
    const r = new FrameReassembler();
    const res = feedAll(r, [values[0], values[1], good[0]]);
    expect(res[2]).toMatchObject({
      status: 'pending',
      groupId: capture.runs[1].groupId,
      dropped: { groupId: capture.runs[0].groupId, receivedBytes: 32, expectedBytes: 77 },
    });
    expect(feedAll(r, good.slice(1)).at(-1)?.status).toBe('complete');
  });

  test('corrupted end marker, bad magic and short values are rejected', () => {
    const r = new FrameReassembler();
    const tail = new Uint8Array(values[4]);
    tail[12] = 0x00; // ED -> 00
    expect(feedAll(r, [...values.slice(0, 4), tail]).at(-1)).toMatchObject({
      status: 'error',
      code: 'bad-end',
    });
    const notFrame = new Uint8Array(values[0]);
    notFrame[0] = 0x00;
    expect(r.push(notFrame)).toMatchObject({ status: 'error', code: 'bad-magic' });
    expect(r.push(new Uint8Array([1, 2, 3]))).toMatchObject({ status: 'error', code: 'short-fragment' });
    expect(r.pending).toBe(false);
  });

  test('unpackFrame validates length', () => {
    const f = packFrame(new Uint8Array([1, 2, 3]));
    expect(() => unpackFrame(f.slice(0, f.length - 1))).toThrow(/declared/);
  });
});

test('negative int32 errorCode (10-byte varint) decodes', () => {
  // isSuccess=false, errorCode=-1 as protobuf-java writes it.
  const body = new Uint8Array([0x40, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x01]);
  const frame = packFrame(
    encodeMessage({ commandId: CMD.HANDSHAKE_RESPONSE, responseSerial: 1 }, body),
  );
  const msg = decodeFrame(frame);
  expect(decodeHandshakeResponse(msg.body)).toMatchObject({ isSuccess: false, errorCode: -1 });
});

test('large frames fragment into 16-byte chunks with increasing fragment numbers', () => {
  const frame = buildWifiCommandFrame(wifiConfigJson({ ssid: 'S'.repeat(32), password: 'x'.repeat(63) }), 3);
  const values = fragmentFrame(frame, 0xabcd);
  expect(values.every(v => v.length <= 20)).toBe(true);
  const r = new FrameReassembler();
  const res = values.map(v => r.push(v));
  const last = res.at(-1);
  expect(last?.status).toBe('complete');
  expect(last && last.status === 'complete' ? hex(last.frame) : '').toBe(hex(frame));
});

describe('Wi-Fi notifications', () => {
  test('parses robot push payloads without exposing scan SSIDs', () => {
    expect(parseWifiNotification('{"co":104,"cd":0}')).toEqual({ co: 104, cd: '0' });
    expect(parseWifiNotification('{"co":104,"cd":"2"}')).toEqual({ co: 104, cd: '2' });
    expect(parseWifiNotification('{"co":-1,"ec":1}')).toEqual({ co: -1, ec: 1 });
    expect(parseWifiNotification('{"co":102}')).toEqual({ co: 102 });
    const list = JSON.stringify([{ s: 'Neighbour', b: '00:11:22:33:44:55' }, { s: 'Other' }]);
    expect(parseWifiNotification(JSON.stringify({ co: 101, p: list }))).toEqual({
      co: 101,
      networkCount: 2,
    });
    expect(parseWifiNotification('not json')).toBeNull();
    expect(parseWifiNotification('{"x":1}')).toBeNull();
  });

  test('utf8 helper matches Buffer', () => {
    expect(hex(utf8Encode('É'))).toBe('C389');
  });
});
