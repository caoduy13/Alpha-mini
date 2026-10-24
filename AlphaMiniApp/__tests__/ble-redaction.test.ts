import { Buffer } from 'buffer';
import {
  bleDiag,
  describeDiagnosticFrame,
  redactDiagnostic,
  rememberDiagnosticSecrets,
} from '../src/ble/diagnostics';
import {
  FrameReassembler,
  buildWifiCommandFrame,
  encodeMessage,
  packFrame,
} from '../src/ble/codec';
import { wifiConfigJson } from '../src/ble/wifi';
import capture from './fixtures/ble-capture-handshake-redacted.json';

/** Values are generated at run time so no credential-like literal lives in this file. */
const runId = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
const fakeWifiValue = `dummy-${runId}`;
const fakeFieldValue = `field-${runId}`;

const forms = (value: string) => [
  value,
  Buffer.from(value, 'utf8').toString('hex'),
  Buffer.from(value, 'utf8').toString('hex').toUpperCase(),
  Buffer.from(value, 'utf8').toString('base64'),
];

function captureFrame(): Uint8Array {
  const r = new FrameReassembler();
  const results = capture.runs[0].fragmentsHex.map(h => r.push(new Uint8Array(Buffer.from(h, 'hex'))));
  const last = results[results.length - 1];
  if (last.status !== 'complete') {
    throw new Error('capture fixture did not reassemble');
  }
  return last.frame;
}

function captureConsole<T>(fn: () => T): { result: T; output: string } {
  const spy = jest.spyOn(console, 'info').mockImplementation(() => {});
  try {
    const result = fn();
    return { result, output: JSON.stringify(spy.mock.calls) };
  } finally {
    spy.mockRestore();
  }
}

test('Wi-Fi request frame: value absent from log output in raw, hex and base64', () => {
  const frame = buildWifiCommandFrame(wifiConfigJson({ ssid: 'test-ssid', password: fakeWifiValue }), 3);
  const { output } = captureConsole(() => bleDiag('frame-send', { note: fakeFieldValue, password: fakeFieldValue }, frame));
  for (const form of forms(fakeWifiValue)) {
    expect(output).not.toContain(form);
  }
  expect(output).toContain('frame-bytes');
});

test('offset masking keeps frame length and header, masks only the data field', () => {
  const frame = buildWifiCommandFrame(wifiConfigJson({ ssid: 'test-ssid', password: fakeWifiValue }), 3);
  const safe = describeDiagnosticFrame(frame);
  expect(safe.format).toBe('mini-ble');
  expect(safe.rawHex).toHaveLength(frame.length * 2);
  expect(safe.rawHex.slice(0, 10)).toBe(Buffer.from(frame.slice(0, 5)).toString('hex'));
  expect(safe.rawHex.endsWith('01ed')).toBe(true);
  expect(safe).toMatchObject({ commandId: 32, sendSerial: 3, wifi: { co: 2 } });
});

test('handshake response: only the session field is masked', () => {
  const frame = captureFrame();
  const safe = describeDiagnosticFrame(frame);
  expect(safe.rawHex).toHaveLength(frame.length * 2);
  expect(safe.rawHex).toContain('2a'.repeat(36));
  for (const form of forms(capture.fakeSessionId)) {
    expect(safe.rawHex).not.toContain(form.toLowerCase());
  }
  expect(safe.rawHex).toContain(Buffer.from('v2.2.5.917').toString('hex'));
});

test('unparseable payload is masked entirely after the 5-byte prefix', () => {
  const frame = buildWifiCommandFrame(wifiConfigJson({ ssid: 'x', password: fakeWifiValue }), 3);
  frame[frame.length - 1] = 0x00;
  const safe = describeDiagnosticFrame(frame);
  expect(safe.format).toBe('opaque');
  expect(safe.rawHex.slice(10)).toBe('2a'.repeat(frame.length - 5));
});

test('unknown command body is masked entirely', () => {
  const body = new Uint8Array(Buffer.from(fakeWifiValue, 'utf8'));
  const frame = packFrame(encodeMessage({ commandId: 77 }, body));
  const safe = describeDiagnosticFrame(frame);
  expect(safe.rawHex).not.toContain(Buffer.from(fakeWifiValue).toString('hex'));
});

test('remembered values are removed from free-text fields', () => {
  rememberDiagnosticSecrets(fakeWifiValue);
  const text = JSON.stringify(redactDiagnostic({ message: `failed with ${fakeWifiValue}`, sessionId: fakeFieldValue }));
  expect(text).not.toContain(fakeWifiValue);
  expect(text).not.toContain(fakeFieldValue);
});

test('a throwing logger does not break the caller', () => {
  const spy = jest.spyOn(console, 'info').mockImplementation(() => {
    throw new Error('sink down');
  });
  try {
    expect(() => bleDiag('probe', {}, new Uint8Array([1, 2, 3]))).not.toThrow();
  } finally {
    spy.mockRestore();
  }
});
