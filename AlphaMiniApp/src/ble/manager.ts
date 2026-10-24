import { bleDiag, bleErrorFields, maskedDeviceId, rememberDiagnosticSecrets } from './diagnostics';
import { BleManager, Device, Subscription } from 'react-native-ble-plx';
import { BLE } from './constants';
import { bytesToBase64, base64ToBytes } from './encoding';
import {
  CMD,
  FrameReassembler,
  type MiniMessage,
  buildHandshakeFrame,
  buildWifiCommandFrame,
  decodeFrame,
  decodeHandshakeResponse,
  decodeWifiResponse,
  fragmentFrame,
  randomGroupId,
} from './codec';
import {
  MESSAGES,
  WIFI_CO,
  type WifiNotification,
  parseWifiNotification,
  quitNetworkConfigJson,
  startNetworkConfigJson,
  wifiConfigJson,
  wifiErrorMessage,
} from './wifi';

export type BleStage =
  | 'idle'
  | 'scanning'
  | 'connecting'
  | 'discovering'
  | 'enabling-indication'
  | 'handshaking'
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
  | { type: 'response'; commandId: number; wifi?: WifiNotification }
  | { type: 'error'; message: string; stage: BleStage }
  /** The robot does not report its IP over BLE; ip stays null. */
  | { type: 'provision-complete'; ip: string | null };

function delay(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

const MAX_QUEUED_MESSAGES = 50;

type MessageWaiter = {
  match: (m: MiniMessage) => boolean;
  resolve: (m: MiniMessage | null) => void;
};

function wifiNotificationOf(m: MiniMessage): WifiNotification | null {
  if (m.header.commandId !== CMD.BIND_OR_SWITCH_WIFI_RESPONSE) {
    return null;
  }
  try {
    return parseWifiNotification(decodeWifiResponse(m.body).data);
  } catch {
    return null;
  }
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

  private messageQueue: MiniMessage[] = [];

  private messageWaiters: MessageWaiter[] = [];

  private reassembler = new FrameReassembler();

  private sendSerial = 0;

  private linkLost = false;

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

  private onIndication(value: Uint8Array) {
    const r = this.reassembler.push(value);
    if (r.status !== 'complete') {
      bleDiag('indication-fragment', {stage: this.currentStage, byteLength: value.length, ...r});
      return;
    }
    let message: MiniMessage;
    try {
      message = decodeFrame(r.frame);
    } catch (error) {
      bleDiag('frame-decode-error', {stage: this.currentStage, ...bleErrorFields(error)}, r.frame);
      return;
    }
    if (message.header.commandId === CMD.HANDSHAKE_RESPONSE) {
      try {
        rememberDiagnosticSecrets(decodeHandshakeResponse(message.body).sessionId);
      } catch {
        /* masked by offset anyway */
      }
    }
    const wifi = wifiNotificationOf(message) ?? undefined;
    bleDiag('frame-received', {stage: this.currentStage, groupId: r.groupId, fragments: r.fragments}, r.frame);
    this.onEvent({ type: 'response', commandId: message.header.commandId, wifi });
    const i = this.messageWaiters.findIndex(w => w.match(message));
    if (i >= 0) {
      const [w] = this.messageWaiters.splice(i, 1);
      w.resolve(message);
      return;
    }
    this.messageQueue.push(message);
    if (this.messageQueue.length > MAX_QUEUED_MESSAGES) {
      this.messageQueue.shift();
    }
  }

  private waitForMessage(
    match: (m: MiniMessage) => boolean,
    timeoutMs: number,
  ): Promise<MiniMessage | null> {
    const queued = this.messageQueue.findIndex(match);
    if (queued >= 0) {
      return Promise.resolve(this.messageQueue.splice(queued, 1)[0]);
    }
    if (this.linkLost) {
      return Promise.resolve(null);
    }
    return new Promise(resolve => {
      const waiter: MessageWaiter = {
        match,
        resolve: m => {
          clearTimeout(timer);
          resolve(m);
        },
      };
      const timer = setTimeout(() => {
        this.messageWaiters = this.messageWaiters.filter(w => w !== waiter);
        resolve(null);
      }, timeoutMs);
      this.messageWaiters.push(waiter);
    });
  }

  private onLinkLost() {
    this.linkLost = true;
    const waiters = this.messageWaiters;
    this.messageWaiters = [];
    waiters.forEach(w => w.resolve(null));
  }

  private async writeFrame(dev: Device, frame: Uint8Array, label: string): Promise<void> {
    const groupId = randomGroupId();
    const values = fragmentFrame(frame, groupId);
    bleDiag('frame-send', {stage: this.currentStage, label, groupId, fragments: values.length}, frame);
    for (const [index, value] of values.entries()) {
      await dev.writeCharacteristicWithResponseForService(
        BLE.SERVICE_UUID,
        BLE.CHAR_WRITE_UUID,
        bytesToBase64(value),
      );
      bleDiag('gatt-write-ack', {label, groupId, fragmentNo: index + 1, byteLength: value.length});
    }
  }

  private nextSerial(): number {
    this.sendSerial += 1;
    return this.sendSerial;
  }

  private async sendWifiCommand(dev: Device, data: string, label: string): Promise<void> {
    await this.writeFrame(dev, buildWifiCommandFrame(data, this.nextSerial()), label);
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
    this.messageQueue = [];
    this.messageWaiters = [];
    this.reassembler.reset();
    this.sendSerial = 0;
    this.linkLost = false;
    let networkConfigStarted = false;

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
          this.onLinkLost();
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
          this.onIndication(base64ToBytes(v));
        },
      );
      bleDiag("monitor-registered", {characteristic: BLE.CHAR_INDICATE_UUID, acknowledgementObserved: false});
      await delay(300);

      this.emitStage('handshaking');
      const handshakeSerial = this.nextSerial();
      await this.writeFrame(dev, buildHandshakeFrame(handshakeSerial), 'handshake');
      const shake = await this.waitForMessage(
        m => m.header.commandId === CMD.HANDSHAKE_RESPONSE && m.header.responseSerial === handshakeSerial,
        BLE.HANDSHAKE_TIMEOUT_MS,
      );
      if (!shake) {
        bleDiag('handshake-timeout', {timeoutMs: BLE.HANDSHAKE_TIMEOUT_MS, linkLost: this.linkLost});
        throw new Error(this.linkLost ? MESSAGES.linkLost : MESSAGES.handshakeTimeout);
      }
      const shakeBody = decodeHandshakeResponse(shake.body);
      bleDiag('handshake-response', {
        isSuccess: shakeBody.isSuccess,
        errorCode: shakeBody.errorCode,
        sysLan: shakeBody.sysLan,
        robotSoftVersionName: shakeBody.robotSoftVersionName,
        btInterfaceVersion: shakeBody.btInterfaceVersion,
        hasSession: shakeBody.sessionId.length > 0,
      });
      if (!shakeBody.isSuccess) {
        throw new Error(MESSAGES.handshakeRejected(shakeBody.errorCode));
      }

      this.emitStage('sending-wifi');
      networkConfigStarted = true;
      await this.sendWifiCommand(dev, startNetworkConfigJson(), 'start-network-config');
      const ready = await this.waitForMessage(
        m => wifiNotificationOf(m)?.co === WIFI_CO.READY,
        BLE.READY_TIMEOUT_MS,
      );
      const readyNote = ready ? wifiNotificationOf(ready) : null;
      bleDiag('network-config-ready', {received: Boolean(ready), cd: readyNote?.cd, timeoutMs: BLE.READY_TIMEOUT_MS});
      if (readyNote && readyNote.cd !== '0') {
        throw new Error(MESSAGES.otherDeviceConfiguring);
      }
      if (!ready && this.linkLost) {
        throw new Error(MESSAGES.linkLost);
      }

      await this.sendWifiCommand(dev, wifiConfigJson({ssid, password}), 'wifi-config');
      this.emitStage('waiting-response');
      const result = await this.waitForMessage(m => {
        const co = wifiNotificationOf(m)?.co;
        return co === WIFI_CO.WIFI_CONNECTED || co === WIFI_CO.ERROR;
      }, BLE.RESPONSE_TIMEOUT_MS);
      const outcome = result ? wifiNotificationOf(result) : null;
      bleDiag('wifi-result', {received: Boolean(result), co: outcome?.co, ec: outcome?.ec, linkLost: this.linkLost, timeoutMs: BLE.RESPONSE_TIMEOUT_MS});
      if (!outcome) {
        throw new Error(this.linkLost ? MESSAGES.linkLostAfterWifi : MESSAGES.wifiTimeout);
      }
      if (outcome.co === WIFI_CO.ERROR) {
        throw new Error(wifiErrorMessage(outcome.ec));
      }

      await this.quitNetworkConfig(dev);
      networkConfigStarted = false;
      bleDiag("provision-complete", {ip: null});
      this.emitStage('success');
      this.onEvent({
        type: 'provision-complete',
        ip: null,
      });
    } catch (e) {
      if (networkConfigStarted && this.device && !this.linkLost) {
        await this.quitNetworkConfig(this.device);
      }
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

  /** Best effort {"co":12}: leaves the robot's BLE network skill; never masks the outcome. */
  private async quitNetworkConfig(dev: Device): Promise<void> {
    try {
      await this.sendWifiCommand(dev, quitNetworkConfigJson(), 'quit-network-config');
    } catch (error) {
      bleDiag('quit-network-config-error', bleErrorFields(error));
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
    this.onLinkLost();
    this.messageQueue = [];
    this.reassembler.reset();
  }

  async disconnect(): Promise<void> {
    this.stopScan("disconnect");
    await this.cleanup();
  }
}
