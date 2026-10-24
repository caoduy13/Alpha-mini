import { BleManager, Device, Subscription } from 'react-native-ble-plx';
import { BLE } from './constants';
import { bytesToBase64, base64ToBytes, bytesToHex } from './encoding';
import { buildAuthPacket, buildWifiConfigPacket } from './protocol';
import {
  extractWifiIp,
  isAuthOk,
  tryParseResponse,
} from './responseParse';

export type BleStage =
  | 'idle'
  | 'scanning'
  | 'connecting'
  | 'discovering'
  | 'enabling-indication'
  | 'authenticating'
  | 'sending-wifi'
  | 'waiting-response'
  | 'success'
  | 'failed';

export type BleEvent =
  | { type: 'stage'; stage: BleStage }
  | {
      type: 'device-found';
      device: { id: string; name: string; rssi: number };
    }
  | { type: 'log'; message: string }
  | { type: 'response'; data: Uint8Array; parsed: unknown }
  | { type: 'error'; message: string; stage: BleStage }
  | { type: 'provision-complete'; ip: string | null };

function delay(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

let sharedBleManager: BleManager | null = null;

export function getBleManager(): BleManager {
  if (!sharedBleManager) {
    sharedBleManager = new BleManager();
  }
  return sharedBleManager;
}

export class AlphaMiniBleClient {
  private readonly ble: BleManager;

  private readonly onEvent: (e: BleEvent) => void;

  private responseQueue: Uint8Array[] = [];

  private responseWaiters: Array<(bytes: Uint8Array) => void> = [];

  private indicationSub: Subscription | null = null;

  private device: Device | null = null;

  private currentStage: BleStage = 'idle';

  private scanTimer: ReturnType<typeof setTimeout> | null = null;

  private finishScan: (() => void) | null = null;

  private clearScanTimer(): void {
    if (this.scanTimer !== null) {
      clearTimeout(this.scanTimer);
      this.scanTimer = null;
    }
  }

  constructor(onEvent: (e: BleEvent) => void, ble?: BleManager) {
    this.onEvent = onEvent;
    this.ble = ble ?? getBleManager();
  }

  private emitStage(stage: BleStage) {
    this.currentStage = stage;
    this.onEvent({ type: 'stage', stage });
  }

  private dispatchResponse(bytes: Uint8Array) {
    if (this.responseWaiters.length > 0) {
      const w = this.responseWaiters.shift()!;
      w(bytes);
    } else {
      this.responseQueue.push(bytes);
    }
  }

  private async waitForResponse(timeoutMs: number): Promise<Uint8Array | null> {
    if (this.responseQueue.length > 0) {
      return this.responseQueue.shift()!;
    }
    return new Promise(resolve => {
      const timer = setTimeout(() => {
        this.responseWaiters = this.responseWaiters.filter(w => w !== waiter);
        resolve(null);
      }, timeoutMs);
      const waiter = (bytes: Uint8Array) => {
        clearTimeout(timer);
        resolve(bytes);
      };
      this.responseWaiters.push(waiter);
    });
  }

  async scan(timeoutMs: number = BLE.SCAN_TIMEOUT_MS): Promise<void> {
    this.stopScan();
    this.emitStage('scanning');
    return new Promise<void>((resolve, reject) => {
      let settled = false;
      const finish = () => {
        if (settled) {
          return;
        }
        settled = true;
        this.clearScanTimer();
        this.finishScan = null;
        this.ble.stopDeviceScan();
        this.emitStage('idle');
        resolve();
      };

      this.finishScan = finish;
      this.ble.startDeviceScan(null, null, (error, scanned) => {
        if (settled) { return; }
        if (error) {
          if (!settled) {
            settled = true;
            this.clearScanTimer();
            this.finishScan = null;
            this.ble.stopDeviceScan();
            this.emitStage('idle');
            reject(error);
          }
          return;
        }
        const name = scanned?.name ?? scanned?.localName ?? '';
        if (name.startsWith(BLE.NAME_PREFIX)) {
          this.onEvent({
            type: 'device-found',
            device: {
              id: scanned!.id,
              name,
              rssi: scanned!.rssi ?? -100,
            },
          });
        }
      });

      if (!settled) {
        this.scanTimer = setTimeout(finish, timeoutMs);
      }
    });
  }

  stopScan(): void {
    this.clearScanTimer();
    if (this.finishScan) {
      this.finishScan();
      return;
    }
    this.ble.stopDeviceScan();
    if (this.currentStage === 'scanning') {
      this.emitStage('idle');
    }
  }

  async provision(
    deviceId: string,
    ssid: string,
    password: string,
  ): Promise<void> {
    this.responseQueue = [];
    this.responseWaiters = [];
    let ipOut: string | null = null;

    try {
      this.emitStage('connecting');
      const dev = await this.ble.connectToDevice(deviceId, {
        timeout: BLE.CONNECT_TIMEOUT_MS,
      });
      this.device = dev;

      this.emitStage('discovering');
      await dev.requestMTU(BLE.MTU_SIZE);
      await delay(200);
      await dev.discoverAllServicesAndCharacteristics();

      this.emitStage('enabling-indication');
      this.indicationSub = dev.monitorCharacteristicForService(
        BLE.SERVICE_UUID,
        BLE.CHAR_INDICATE_UUID,
        (error, characteristic) => {
          if (error) {
            this.onEvent({
              type: 'error',
              message: error.message,
              stage: this.currentStage,
            });
            return;
          }
          const v = characteristic?.value;
          if (!v) {
            return;
          }
          const bytes = base64ToBytes(v);
          const parsed = tryParseResponse(bytes);
          this.onEvent({ type: 'response', data: bytes, parsed });
          this.dispatchResponse(bytes);
        },
      );
      await delay(300);

      this.emitStage('authenticating');
      const { packet: authPacket, salt } = buildAuthPacket();
      this.onEvent({ type: 'log', message: `Auth salt=${salt}` });
      await dev.writeCharacteristicWithResponseForService(
        BLE.SERVICE_UUID,
        BLE.CHAR_WRITE_UUID,
        bytesToBase64(authPacket),
      );

      const authResp = await this.waitForResponse(10000);
      if (!isAuthOk(authResp)) {
        throw new Error(
          `Auth failed: ${authResp ? bytesToHex(authResp) : 'timeout'}`,
        );
      }
      await delay(300);

      this.emitStage('sending-wifi');
      const wifiPacket = buildWifiConfigPacket(ssid, password);
      await dev.writeCharacteristicWithResponseForService(
        BLE.SERVICE_UUID,
        BLE.CHAR_WRITE_UUID,
        bytesToBase64(wifiPacket),
      );

      this.emitStage('waiting-response');
      const wifiResp = await this.waitForResponse(BLE.RESPONSE_TIMEOUT_MS);
      if (!wifiResp) {
        throw new Error('Robot WiFi response timeout');
      }
      const wifiParsed = tryParseResponse(wifiResp);
      ipOut = wifiParsed ? extractWifiIp(wifiParsed.payload) : null;

      this.emitStage('success');
      this.onEvent({
        type: 'provision-complete',
        ip: ipOut,
      });
    } catch (e) {
      const failStage = this.currentStage;
      this.emitStage('failed');
      this.onEvent({
        type: 'error',
        message: e instanceof Error ? e.message : String(e),
        stage: failStage,
      });
      throw e;
    } finally {
      await this.cleanup();
    }
  }

  private async cleanup() {
    try {
      this.indicationSub?.remove();
      this.indicationSub = null;
      if (this.device) {
        await this.device.cancelConnection();
      }
    } catch {
      /* ignore */
    }
    this.device = null;
    this.responseQueue = [];
    this.responseWaiters = [];
  }

  async disconnect(): Promise<void> {
    this.stopScan();
    await this.cleanup();
  }
}
