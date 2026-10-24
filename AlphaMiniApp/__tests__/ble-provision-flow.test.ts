/**
 * Luồng provisioning BLE end-to-end với robot giả lập.
 *
 * Robot giả: nhận frame app ghi vào characteristic write, trả lời bằng
 * indication theo đúng giao thức trong docs/ble-protocol.md:
 *   handshake (command 0)  -> 5 mảnh capture thật (đã che session)
 *   co=4                   -> {"co":104,"cd":0}
 *   co=2                   -> {"co":102} (thành công) hoặc {"co":-1,"ec":1} (sai mật khẩu)
 *   co=12                  -> không trả lời
 *
 * Giá trị Wi-Fi trong test được sinh lúc chạy, không cố định trong file.
 */
import { Buffer } from 'buffer';
import { BleManager, type Device } from 'react-native-ble-plx';
import { AlphaMiniBleClient, type BleEvent } from '../src/ble/manager';
import * as codec from '../src/ble/codec';
import * as wifi from '../src/ble/wifi';
import golden from './fixtures/ble-golden-sdk.json';
import capture from './fixtures/ble-capture-handshake-redacted.json';

// ======================= ADAPT =======================
// Chỉ nối các hàm dưới với export THẬT của codec.ts / wifi.ts / fixtures.
// Không đổi chữ ký hàm, không đổi phần test bên dưới.

type Sent = {
  command: number; // 0 = handshake, 32 = Wi-Fi
  serial: number; // sendSerial
  co?: number; // trường co trong body Wi-Fi; undefined với handshake
  base64: string; // frame LOGIC đã ghép đủ mảnh, bỏ trailer (groupId app chọn ngẫu nhiên)
};

const toB64 = (u: Uint8Array) => Buffer.from(u).toString('base64');
const fromB64 = (s: string) => new Uint8Array(Buffer.from(s, 'base64'));
const fromHex = (h: string) => new Uint8Array(Buffer.from(h, 'hex'));

/**
 * Bộ ghép mảnh phía robot: nhận từng lần ghi GATT (base64, tối đa 20 byte),
 * trả về base64 của frame logic khi mảnh cuối hoàn chỉnh, ngược lại trả null.
 * Mỗi lần gọi runFlow tạo một bộ ghép mới.
 */
function makeReassembler(): (fragmentB64: string) => string | null {
  const reassembler = new codec.FrameReassembler();
  return fragmentB64 => {
    const result = reassembler.push(fromB64(fragmentB64));
    if (result.status === 'error') {
      throw new Error(`robot reassembly ${result.code}: ${result.message}`);
    }
    return result.status === 'complete' ? toB64(result.frame) : null;
  };
}

/** Giải mã một frame logic hoàn chỉnh (base64 do makeReassembler trả về) thành Sent. */
function decodeSent(b64: string): Sent {
  const { header, body } = codec.decodeFrame(fromB64(b64));
  const co =
    header.commandId === codec.CMD.BIND_OR_SWITCH_WIFI
      ? wifi.parseWifiNotification(codec.decodeWifiRequest(body).data)?.co
      : undefined;
  return { command: header.commandId, serial: header.sendSerial, co, base64: b64 };
}

/** Các mảnh indication (base64) của phản hồi handshake thật, đã che session. */
function handshakeReply(): string[] {
  return capture.runs[0].fragmentsHex.map(h => toB64(fromHex(h)));
}

let notifySerial = 0;
/** Mã hóa một thông báo Wi-Fi robot đẩy về (command 1032) thành các mảnh base64. */
function wifiNotify(payload: Record<string, unknown>): string[] {
  notifySerial += 1;
  // BindOrSwitchWifiResponse{data=1} có cùng field 1 với request; versionCode 0 bị bỏ khỏi wire.
  const frame = codec.packFrame(
    codec.encodeMessage(
      {
        commandId: codec.CMD.BIND_OR_SWITCH_WIFI_RESPONSE,
        sendSerial: notifySerial,
        versionCode: 1,
        msgType: codec.MSG_TYPE.REQUEST,
      },
      codec.encodeWifiRequest(JSON.stringify(payload), 0),
    ),
  );
  return codec.fragmentFrame(frame, 0x4000 + notifySerial).map(toB64);
}

/** SSID/mật khẩu giả và chuỗi frame (base64) mà SDK sinh cho handshake -> co=4 -> co=2 -> co=12. */
function goldenChain(): { ssid: string; pass: string; frames: string[] } {
  const { s, p } = JSON.parse(golden.wifiConfig.data) as { s: string; p: string };
  return {
    ssid: s,
    pass: p,
    frames: [
      golden.handshakeRequest,
      golden.startNetworkConfig,
      golden.wifiConfig,
      golden.exitNetworkConfig,
    ].map(v => toB64(fromHex(v.frameHex))),
  };
}

/** Kiểm tra provisioning thành công trong danh sách sự kiện. */
const isComplete = (e: BleEvent) => (e as { type?: string }).type === 'provision-complete';
// ===================== HẾT ADAPT =====================

type Plan = 'success' | 'wrongPassword';

async function runFlow(ssid: string, pass: string, plan: Plan) {
  const ble = new BleManager();
  const sent: Sent[] = [];
  const reassemble = makeReassembler();
  let indicate: ((error: null, characteristic: { value: string }) => void) | undefined;

  const pushChunks = (chunks: string[]) => {
    for (const value of chunks) indicate?.(null, { value });
  };

  const reply = (msg: Sent) => {
    if (msg.command === 0) pushChunks(handshakeReply());
    else if (msg.co === 4) pushChunks(wifiNotify({ co: 104, cd: 0 }));
    else if (msg.co === 2) {
      pushChunks(wifiNotify(plan === 'success' ? { co: 102 } : { co: -1, ec: 1 }));
    }
    // co=12: robot không trả lời
  };

  const device = {
    id: 'robot-test',
    mtu: 517,
    requestMTU: jest.fn(async () => ({ mtu: 517 })),
    discoverAllServicesAndCharacteristics: jest.fn(async () => ({})),
    onDisconnected: jest.fn(() => ({ remove: jest.fn() })),
    monitorCharacteristicForService: jest.fn(
      (_service: string, _characteristic: string, callback: typeof indicate) => {
        indicate = callback;
        return { remove: jest.fn() };
      },
    ),
    writeCharacteristicWithResponseForService: jest.fn(
      async (_service: string, _characteristic: string, fragmentB64: string) => {
        const frame = reassemble(fragmentB64);
        if (frame !== null) {
          const msg = decodeSent(frame);
          sent.push(msg);
          setTimeout(() => reply(msg), 0);
        }
        return {};
      },
    ),
    cancelConnection: jest.fn(async () => ({})),
  };

  (ble.connectToDevice as jest.Mock).mockResolvedValue(device as unknown as Device);

  const events: BleEvent[] = [];
  const client = new AlphaMiniBleClient(e => events.push(e), ble);
  const pending = client.provision('robot-test', ssid, pass).then(
    value => ({ ok: true as const, value }),
    error => ({ ok: false as const, error }),
  );
  await jest.runAllTimersAsync();
  const outcome = await pending;
  return { sent, events, outcome, device };
}

const fakeValue = (prefix: string) =>
  `${prefix}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

describe('BLE provisioning flow (robot giả lập)', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it('gửi đúng chuỗi frame như SDK: handshake -> co=4 -> co=2 -> co=12', async () => {
    const g = goldenChain();
    const { sent, events } = await runFlow(g.ssid, g.pass, 'success');

    expect(sent.map(s => (s.command === 0 ? 'handshake' : s.co))).toEqual([
      'handshake',
      4,
      2,
      12,
    ]);
    expect(sent.map(s => s.serial)).toEqual([1, 2, 3, 4]);
    expect(sent.map(s => s.base64)).toEqual(g.frames);
    expect(events.some(isComplete)).toBe(true);
  });

  it('robot báo ec=1 -> người dùng thấy thông báo sai mật khẩu bằng tiếng Việt', async () => {
    const { events, outcome } = await runFlow(fakeValue('net-'), fakeValue('pw-'), 'wrongPassword');

    expect(events.some(isComplete)).toBe(false);
    const visible = JSON.stringify(events) + (outcome.ok ? '' : String(outcome.error));
    expect(visible).toContain('Sai mật khẩu Wi-Fi');
  });

  it('mật khẩu không xuất hiện trong console ở dạng thô, hex hay base64', async () => {
    const output: string[] = [];
    const capture = (...args: unknown[]) => {
      output.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' '));
    };
    for (const level of ['log', 'info', 'warn', 'error', 'debug'] as const) {
      jest.spyOn(console, level).mockImplementation(capture);
    }

    const pass = fakeValue('pw-');
    const ok = await runFlow(fakeValue('net-'), pass, 'success');
    const bad = await runFlow(fakeValue('net-'), pass, 'wrongPassword');

    // Chống pass "ảo": frame co=2 (chứa mật khẩu) phải thực sự được gửi ở cả hai lượt.
    expect(ok.sent.some(s => s.co === 2)).toBe(true);
    expect(bad.sent.some(s => s.co === 2)).toBe(true);

    const all = output.join('\n');
    expect(output.length).toBeGreaterThan(0); // log thật sự đã chạy
    const hex = Buffer.from(pass, 'utf8').toString('hex');
    for (const form of [
      pass,
      hex,
      hex.toUpperCase(),
      Buffer.from(pass, 'utf8').toString('base64'),
    ]) {
      expect(all).not.toContain(form);
    }
  });
});
