import { bleDiag, bleErrorFields, describeDiagnosticFrame, maskedDeviceId, rememberDiagnosticSecrets } from './diagnostics';
import { BleManager, Device, Subscription } from 'react-native-ble-plx';
import { BLE } from './constants';
import { bytesToBase64, base64ToBytes } from './encoding';
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

  private stageStartedAt = Date.now();
  private scanSequence = 0;
  private disconnectionSub: Subscription | null = null;

  private scanTimer: ReturnType<typeof setTimeout> | null = null;

  private finishScan: ((reason?: string) => void) | null = null;

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
    bleDiag("gatt-stage", {previousStage: this.currentStage, stage, elapsedMs: Date.now() - this.stageStartedAt});
    this.stageStartedAt = Date.now();
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
    this.stopScan("restart");
    const scanId = ++this.scanSequence;
    const startedAt = Date.now();
    let rawCount = 0;
    let matchedCount = 0;
    bleDiag("scan-start", {scanId, timeoutMs, namePrefix: BLE.NAME_PREFIX, serviceFilter: null});
    this.emitStage('scanning');
    return new Promise<void>((resolve, reject) => {
      let settled = false;
      const finish = (reason = "timeout") => {
        if (settled) {
          return;
        }
        settled = true;
        bleDiag("scan-stop", {scanId, reason, elapsedMs: Date.now() - startedAt, rawCount, matchedCount});
        this.clearScanTimer();
        this.finishScan = null;
        this.ble.stopDeviceScan();
        this.emitStage('idle');
        resolve();
      };

      this.finishScan = finish;
      this.ble.startDeviceScan(null, null, (error, scanned) => {
        if (settled) { bleDiag("scan-late-callback", {scanId}); return; }
        if (error) {
          bleDiag("scan-error", {scanId, elapsedMs: Date.now() - startedAt, ...bleErrorFields(error)});
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
        rawCount++;
        const matched = name.toUpperCase().startsWith(BLE.NAME_PREFIX);
        if (matched) { matchedCount++; }
        bleDiag('scan-device', {scanId, deviceId: maskedDeviceId(scanned?.id ?? ''), name: scanned?.name, localName: scanned?.localName, rssi: scanned?.rssi, serviceUUIDs: scanned?.serviceUUIDs, matched, reason: matched ? 'name-prefix-match' : name ? 'name-prefix-mismatch' : 'missing-name'});
        if (matched) {
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

  stopScan(reason = "manual"): void {
    this.clearScanTimer();
    if (this.finishScan) {
      this.finishScan(reason);
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
    rememberDiagnosticSecrets(password);
    bleDiag("provision-start", {deviceId: maskedDeviceId(deviceId), ssid, wifiSecured: Boolean(password), connectTimeoutMs: BLE.CONNECT_TIMEOUT_MS});
    this.responseQueue = [];
    this.responseWaiters = [];
    let ipOut: string | null = null;

    try {
      this.emitStage('connecting');
      const dev = await this.ble.connectToDevice(deviceId, {
        timeout: BLE.CONNECT_TIMEOUT_MS,
      });
      this.device = dev;
      bleDiag('connect-complete', {deviceId: maskedDeviceId(dev.id), mtu: dev.mtu});
      try {
        this.disconnectionSub = dev.onDisconnected(error => {
          bleDiag('disconnected', {deviceId: maskedDeviceId(dev.id), stage: this.currentStage, ...(error ? bleErrorFields(error) : {})});
        });
      } catch (error) { bleDiag('disconnect-observer-error', bleErrorFields(error)); }

      this.emitStage('discovering');
      const mtuDevice = await dev.requestMTU(BLE.MTU_SIZE);
      bleDiag("mtu-complete", {requested: BLE.MTU_SIZE, negotiated: mtuDevice.mtu});
      await delay(200);
      await dev.discoverAllServicesAndCharacteristics();
      bleDiag("discovery-complete", {service: BLE.SERVICE_UUID, writeCharacteristic: BLE.CHAR_WRITE_UUID, indicationCharacteristic: BLE.CHAR_INDICATE_UUID});

      this.emitStage('enabling-indication');
      this.indicationSub = dev.monitorCharacteristicForService(
        BLE.SERVICE_UUID,
        BLE.CHAR_INDICATE_UUID,
        (error, characteristic) => {
          if (error) {
            bleDiag("indication-error", {stage: this.currentStage, ...bleErrorFields(error)});
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
          bleDiag("response", {stage: this.currentStage, parsed}, bytes);
          this.onEvent({ type: 'response', data: bytes, parsed });
          this.dispatchResponse(bytes);
        },
      );
      bleDiag("monitor-registered", {characteristic: BLE.CHAR_INDICATE_UUID, acknowledgementObserved: false});
      await delay(300);

      this.emitStage('authenticating');
      const { packet: authPacket } = buildAuthPacket();
      bleDiag("auth-request", {}, authPacket);
      await dev.writeCharacteristicWithResponseForService(
        BLE.SERVICE_UUID,
        BLE.CHAR_WRITE_UUID,
        bytesToBase64(authPacket),
      );

      const authResp = await this.waitForResponse(10000);
      bleDiag("auth-response", {timedOut: authResp === null, timeoutMs: 10000}, authResp ?? undefined);
      if (!isAuthOk(authResp)) {
        throw new Error(
          `Auth failed: ${authResp ? JSON.stringify(describeDiagnosticFrame(authResp)) : 'timeout'}`,
        );
      }
      await delay(300);

      this.emitStage('sending-wifi');
      const wifiPacket = buildWifiConfigPacket(ssid, password);
      bleDiag("wifi-request", {}, wifiPacket);
      await dev.writeCharacteristicWithResponseForService(
        BLE.SERVICE_UUID,
        BLE.CHAR_WRITE_UUID,
        bytesToBase64(wifiPacket),
      );

      this.emitStage('waiting-response');
      const wifiResp = await this.waitForResponse(BLE.RESPONSE_TIMEOUT_MS);
      bleDiag("wifi-response", {timedOut: wifiResp === null, timeoutMs: BLE.RESPONSE_TIMEOUT_MS}, wifiResp ?? undefined);
      if (!wifiResp) {
        throw new Error('Robot WiFi response timeout');
      }
      const wifiParsed = tryParseResponse(wifiResp);
      ipOut = wifiParsed ? extractWifiIp(wifiParsed.payload) : null;

      bleDiag("provision-complete", {ip: ipOut});
      this.emitStage('success');
      this.onEvent({
        type: 'provision-complete',
        ip: ipOut,
      });
    } catch (e) {
      const failStage = this.currentStage;
      bleDiag("provision-error", {stage: failStage, ...bleErrorFields(e)});
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
    bleDiag("disconnect-start", {deviceId: this.device ? maskedDeviceId(this.device.id) : null, stage: this.currentStage});
    try {
      this.disconnectionSub?.remove();
    } catch (error) {
      bleDiag("disconnect-observer-cleanup-error", bleErrorFields(error));
    }
    this.disconnectionSub = null;
    try {
      this.indicationSub?.remove();
      this.indicationSub = null;
      if (this.device) {
        await this.device.cancelConnection();
      }
    } catch (error) {
      bleDiag("disconnect-error", bleErrorFields(error));
    }
    bleDiag("disconnect-cleanup-complete", {deviceId: this.device ? maskedDeviceId(this.device.id) : null});
    this.device = null;
    this.responseQueue = [];
    this.responseWaiters = [];
  }

  async disconnect(): Promise<void> {
    this.stopScan("disconnect");
    await this.cleanup();
  }
}
