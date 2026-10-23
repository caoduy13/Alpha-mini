import CryptoJS from 'crypto-js';
import { PROTOCOL } from './constants';

export function frame(method: number, payloadJson: string): Uint8Array {
  const payloadBytes = new TextEncoder().encode(payloadJson);
  const totalLen = 1 + payloadBytes.length;
  const buf = new Uint8Array(4 + totalLen);
  buf[0] = (totalLen >>> 24) & 0xff;
  buf[1] = (totalLen >>> 16) & 0xff;
  buf[2] = (totalLen >>> 8) & 0xff;
  buf[3] = totalLen & 0xff;
  buf[4] = method & 0xff;
  buf.set(payloadBytes, 5);
  return buf;
}

export function randomSalt(): string {
  const a = PROTOCOL.SALT_ALPHABET;
  let s = '';
  for (let i = 0; i < PROTOCOL.SALT_LENGTH; i++) {
    s += a[Math.floor(Math.random() * a.length)];
  }
  return s;
}

export function buildAuthPacket(salt?: string): {
  packet: Uint8Array;
  salt: string;
} {
  const s = salt ?? randomSalt();
  const md5Wa = CryptoJS.MD5(
    CryptoJS.enc.Utf8.parse(PROTOCOL.USER_ID + s),
  );
  const keyWa = CryptoJS.enc.Utf8.parse(PROTOCOL.AES_KEY);
  const encrypted = CryptoJS.AES.encrypt(md5Wa, keyWa, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7,
  });
  const token = CryptoJS.enc.Base64.stringify(encrypted.ciphertext);

  const json = `{
  "VersionCode": 1,
  "EncryAlgorithm": "AES128",
  "UserId": "${PROTOCOL.USER_ID}",
  "salt": "${s}",
  "token": "${token}"
}`;

  return {
    packet: frame(PROTOCOL.METHOD_AUTH, json),
    salt: s,
  };
}

export function buildWifiConfigPacket(ssid: string, password: string): Uint8Array {
  const json = `{
  "cmd": "wifi_config",
  "ssid": ${JSON.stringify(ssid)},
  "password": ${JSON.stringify(password)}
}`;
  return frame(PROTOCOL.METHOD_WIFI_CONFIG, json);
}
