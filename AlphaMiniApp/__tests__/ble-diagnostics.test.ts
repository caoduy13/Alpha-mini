import {BleManager, type Device} from 'react-native-ble-plx';
import {AlphaMiniBleClient, type BleEvent} from '../src/ble/manager';
import {BLE, PROTOCOL} from '../src/ble/constants';
import {Buffer} from 'buffer';
import {
  bleDiag,
  describeDiagnosticFrame,
  redactDiagnostic,
} from '../src/ble/diagnostics';
import {frame} from '../src/ble/protocol';
it('redacts protected fields recursively, including casing and AES keys', () => {
  const safe = JSON.stringify(
    redactDiagnostic({
      PASSWORD: 'wifi-secret',
      nested: [
        {token: 'token-secret', salt: 'salt-secret', AES_KEY: 'key-secret'},
      ],
      status: 'ok',
    }),
  );
  for (const secret of [
    'wifi-secret',
    'token-secret',
    'salt-secret',
    'key-secret',
  ]) {
    expect(safe).not.toContain(secret);
  }
  expect(safe).toContain('ok');
});
it('preserves full frame offsets/header while masking sensitive values', () => {
  const input = frame(
    2,
    JSON.stringify({
      status: 'ok',
      password: 'pass-unique-42',
      nested: {salt: 'salt-unique-42', token: 'token-unique-42'},
      aes_key: 'aes-unique-42',
    }),
  );
  const original = new Uint8Array(input);
  const safe = describeDiagnosticFrame(input);
  expect(safe.rawHex).toHaveLength(input.length * 2);
  expect(safe.rawHex.slice(0, 10)).toBe(
    Buffer.from(input.slice(0, 5)).toString('hex'),
  );
  expect(safe.rawHex).toContain(Buffer.from('"status":"ok"').toString('hex'));
  for (const secret of [
    'pass-unique-42',
    'salt-unique-42',
    'token-unique-42',
    'aes-unique-42',
  ]) {
    expect(safe.rawHex).not.toContain(Buffer.from(secret).toString('hex'));
  }
  expect(input).toEqual(original);
});
it('fails closed for opaque payloads', () => {
  const input = frame(1, 'not-json-private-token');
  const safe = describeDiagnosticFrame(input);
  expect(safe.format).toBe('opaque');
  expect(safe.rawHex.slice(10)).toBe('2a'.repeat(input.length - 5));
});
it('logs every redacted byte in ordered chunks without credential values', () => {
  const spy = jest.spyOn(console, 'info').mockImplementation(() => {});
  try {
    const input = frame(
      1,
      JSON.stringify({
        salt: 'salt-private-value',
        token: 'token-private-value',
        status: 'ok',
        padding: '.'.repeat(800),
      }),
    );
    bleDiag('auth-response', {token: 'field-private-value'}, input);
    const lines = spy.mock.calls.map(call => JSON.parse(call[1]));
    const chunks = lines.filter(line => line.event === 'frame-bytes');
    expect(chunks.length).toBeGreaterThan(1);
    expect(chunks.map(chunk => chunk.hex).join('')).toBe(
      describeDiagnosticFrame(input).rawHex,
    );
    expect(chunks.at(-1).last).toBe(true);
    const output = JSON.stringify(spy.mock.calls);
    for (const secret of [
      'salt-private-value',
      'token-private-value',
      'field-private-value',
    ]) {
      expect(output).not.toContain(secret);
      expect(output).not.toContain(Buffer.from(secret).toString('hex'));
    }
  } finally {
    spy.mockRestore();
  }
});
it('redacts credentials from errors and URL query/userinfo', () => {
  const text = JSON.stringify(
    redactDiagnostic({
      message: 'token=private-value password="private-password"',
      serverUrl: 'https://user:pass@host/path?token=hidden',
    }),
  );
  for (const secret of [
    'private-value',
    'private-password',
    'user:pass',
    'token=hidden',
  ]) {
    expect(text).not.toContain(secret);
  }
});

it('masks escaped keys and multibyte credentials at original byte offsets', () => {
  const secret = 'wifi-\u00e9\\"secret';
  const input = frame(
    2,
    '{"\\u0074oken":"escaped-key-secret","password":' +
      JSON.stringify(secret) +
      ',"status":"ok"}',
  );
  const safe = describeDiagnosticFrame(input);
  expect(safe.rawHex).toHaveLength(input.length * 2);
  expect(safe.rawHex).not.toContain(
    Buffer.from('escaped-key-secret').toString('hex'),
  );
  expect(safe.rawHex).not.toContain(Buffer.from(secret).toString('hex'));
  expect(safe.rawHex).toContain(Buffer.from('"status":"ok"').toString('hex'));
});
it('masks nested secret objects, arrays and non-string values', () => {
  const input = frame(
    2,
    JSON.stringify({
      credentials: {value: 'opaque-secret'},
      token: 123456789,
      salt: true,
      password: ['array-secret'],
      status: 'ok',
    }),
  );
  const safe = describeDiagnosticFrame(input);
  for (const value of ['opaque-secret', '123456789', 'true', 'array-secret']) {
    expect(safe.rawHex).not.toContain(Buffer.from(value).toString('hex'));
  }
  expect(safe.rawHex).toContain(Buffer.from('"status":"ok"').toString('hex'));
});

it('does not change control flow if the log sink throws', () => {
  const spy = jest.spyOn(console, 'info').mockImplementation(() => {
    throw new Error('log sink unavailable');
  });
  try {
    expect(() => bleDiag('probe', {}, new Uint8Array([1, 2, 3]))).not.toThrow();
  } finally {
    spy.mockRestore();
  }
});

it('observes provisioning without modifying wire credentials, MTU or success handling', async () => {
  jest.useFakeTimers();
  const spy = jest.spyOn(console, 'info').mockImplementation(() => {});
  const ble = new BleManager();
  let notify: (error: null, characteristic: {value: string}) => void;
  const sent: Uint8Array[] = [];
  const device = {
    id: 'robot-diag',
    mtu: BLE.MTU_SIZE,
    requestMTU: jest.fn(async () => ({mtu: BLE.MTU_SIZE})),
    discoverAllServicesAndCharacteristics: jest.fn(async () => {}),
    onDisconnected: jest.fn(() => ({remove: jest.fn()})),
    monitorCharacteristicForService: jest.fn((_s, _c, callback) => {
      notify = callback;
      return {remove: jest.fn()};
    }),
    writeCharacteristicWithResponseForService: jest.fn(
      async (_s, _c, encoded: string) => {
        const bytes = new Uint8Array(Buffer.from(encoded, 'base64'));
        sent.push(bytes);
        const response = frame(
          bytes[4],
          JSON.stringify(
            bytes[4] === 1
              ? {
                  status: 'success',
                  salt: 'reply-private-salt',
                  token: 'reply-private-token',
                }
              : {code: 0, ip: '192.0.2.10'},
          ),
        );
        notify(null, {value: Buffer.from(response).toString('base64')});
      },
    ),
    cancelConnection: jest.fn(async () => {}),
  };
  (ble.connectToDevice as jest.Mock).mockResolvedValue(
    device as unknown as Device,
  );
  const events: BleEvent[] = [];
  try {
    const client = new AlphaMiniBleClient(event => events.push(event), ble);
    const result = client.provision(
      'robot-diag',
      'test-network',
      'wifi-private-password',
    );
    await jest.runAllTimersAsync();
    await result;
    expect(ble.connectToDevice).toHaveBeenCalledWith('robot-diag', {
      timeout: BLE.CONNECT_TIMEOUT_MS,
    });
    expect(device.requestMTU).toHaveBeenCalledWith(512);
    expect(
      JSON.parse(new TextDecoder().decode(sent[1].slice(5))).password,
    ).toBe('wifi-private-password');
    expect(events).toContainEqual({
      type: 'provision-complete',
      ip: '192.0.2.10',
    });
    const auth = JSON.parse(new TextDecoder().decode(sent[0].slice(5)));
    const output = JSON.stringify(spy.mock.calls);
    for (const secret of [
      'wifi-private-password',
      'reply-private-salt',
      'reply-private-token',
      auth.salt,
      auth.token,
      PROTOCOL.AES_KEY,
    ]) {
      expect(output).not.toContain(secret);
      expect(output).not.toContain(Buffer.from(secret).toString('hex'));
    }
  } finally {
    spy.mockRestore();
    jest.clearAllTimers();
    jest.useRealTimers();
  }
});

it('fails closed if a BOM would shift the decoded JSON byte offsets', () => {
  const encoded = new TextEncoder().encode(
    JSON.stringify({token: 'bom-private-token', status: 'ok'}),
  );
  const input = new Uint8Array(encoded.length + 3);
  input.set([0xef, 0xbb, 0xbf]);
  input.set(encoded, 3);
  const safe = describeDiagnosticFrame(input);
  expect(safe.format).toBe('opaque');
  expect(safe.rawHex).toBe('2a'.repeat(input.length));
});
