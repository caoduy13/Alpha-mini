import { useCallback, useEffect, useRef, useState } from 'react';
import type { BleStage } from '../ble/manager';
import { AlphaMiniBleClient } from '../ble/manager';
import { redactDiagnostic } from '../ble/diagnostics';

export type BleDeviceRow = { id: string; name: string; rssi: number };

export function useBleProvisioning() {
  const [stage, setStage] = useState<BleStage>('idle');
  const [devices, setDevices] = useState<BleDeviceRow[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [resultIp, setResultIp] = useState<string | null>(null);
  const [lastErrorStage, setLastErrorStage] = useState<BleStage | null>(null);

  const clientRef = useRef<AlphaMiniBleClient | null>(null);

  const pushLog = useCallback((msg: string) => {
    setLogs(prev => [...prev.slice(-120), String(redactDiagnostic(msg))]);
  }, []);

  useEffect(() => {
    const client = new AlphaMiniBleClient(ev => {
      if (ev.type === 'stage') {
        setStage(ev.stage);
      }
      if (ev.type === 'device-found') {
        setDevices(prev => {
          const others = prev.filter(d => d.id !== ev.device.id);
          return [...others, ev.device].sort((a, b) => b.rssi - a.rssi);
        });
      }
      if (ev.type === 'log') {
        pushLog(ev.message);
      }
      if (ev.type === 'response') {
        pushLog('response received; see [BLE-DIAG] redacted frame-bytes');
      }
      if (ev.type === 'error') {
        setError(ev.message);
        setLastErrorStage(ev.stage);
        pushLog(`ERR [${ev.stage}] ${ev.message}`);
      }
      if (ev.type === 'provision-complete') {
        setResultIp(ev.ip);
        pushLog(`provision-complete ip=${ev.ip ?? 'n/a'}`);
      }
    });
    clientRef.current = client;
    return () => {
      void client.disconnect();
      clientRef.current = null;
    };
  }, [pushLog]);

  const startScan = useCallback(async () => {
    const c = clientRef.current;
    if (!c) {
      return;
    }
    setError(null);
    setLastErrorStage(null);
    setDevices([]);
    try {
      await c.scan();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const stopScanOnly = useCallback(() => {
    clientRef.current?.stopScan();
  }, []);

  const provision = useCallback(
    async (deviceId: string, ssid: string, password: string) => {
      const c = clientRef.current;
      if (!c) {
        return;
      }
      setError(null);
      setLastErrorStage(null);
      setResultIp(null);
      try {
        await c.provision(deviceId, ssid, password);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [],
  );

  const cancel = useCallback(async () => {
    await clientRef.current?.disconnect();
    setStage('idle');
    setError(null);
    setLastErrorStage(null);
  }, []);

  return {
    stage,
    devices,
    logs,
    error,
    resultIp,
    lastErrorStage,
    startScan,
    stopScanOnly,
    provision,
    cancel,
  };
}
