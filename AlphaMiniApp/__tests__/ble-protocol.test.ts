import {
  buildAuthPacket,
  buildWifiConfigPacket,
  frame,
  randomSalt,
} from '../src/ble/protocol';

/** Golden vector: Node crypto matching BleProtocol.kt, salt abcd1234 */
const GOLDEN_AUTH_PACKET_HEX =
  '000000a4017b0a20202256657273696f6e436f6465223a20312c0a202022456e637279416c676f726974686d223a2022414553313238222c0a202022557365724964223a2022616c7068616d696e695f75736572222c0a20202273616c74223a20226162636431323334222c0a202022746f6b656e223a202273684f4f3239775377676377506e476d4239593363433468724e3234484c58486c456a4241694443676c733d220a7d';

function u8ToHex(u: Uint8Array): string {
  return Array.from(u)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

describe('ble protocol', () => {
  test('frame layout: totalLen = 1 + payload, BE 4 bytes', () => {
    const f = frame(0x01, 'abc');
    expect(Array.from(f)).toEqual([0, 0, 0, 4, 0x01, 0x61, 0x62, 0x63]);
  });

  test('buildAuthPacket fixed salt matches Kotlin/Java crypto golden hex', () => {
    const { packet, salt } = buildAuthPacket('abcd1234');
    expect(salt).toBe('abcd1234');
    expect(packet[4]).toBe(0x01);
    expect(u8ToHex(packet)).toBe(GOLDEN_AUTH_PACKET_HEX);
  });

  test('buildAuthPacket fixed salt is deterministic', () => {
    const a = buildAuthPacket('abcd1234').packet;
    const b = buildAuthPacket('abcd1234').packet;
    expect(u8ToHex(a)).toBe(u8ToHex(b));
  });

  test('buildWifiConfigPacket method byte and JSON', () => {
    const p = buildWifiConfigPacket('My Wifi', 'secret"quote');
    expect(p[4]).toBe(0x02);
    const json = new TextDecoder().decode(p.slice(5));
    expect(json).toContain('"ssid": "My Wifi"');
    expect(json).toContain('\\"quote');
  });

  test('randomSalt length and alphabet', () => {
    const s = randomSalt();
    expect(s.length).toBe(8);
    expect(/^[a-z0-9]+$/.test(s)).toBe(true);
  });
});
