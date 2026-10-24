import { bleDiag } from './diagnostics';
import { PermissionsAndroid, Platform } from 'react-native';

export async function requestBlePermissions(): Promise<{
  ok: boolean;
  missing: string[];
}> {
  bleDiag('permission-request', {platform: Platform.OS, apiLevel: Platform.Version});
  if (Platform.OS !== 'android') {
    return { ok: true, missing: [] };
  }

  const apiLevel = Platform.Version as number;

  if (apiLevel >= 31) {
    const results = await PermissionsAndroid.requestMultiple([
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
    ]);
    const ps = [
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
    ];
    bleDiag('permission-result', {apiLevel, results});
    const missing = ps.filter(
      p => results[p] !== PermissionsAndroid.RESULTS.GRANTED,
    );
    return { ok: missing.length === 0, missing };
  }

  const p = PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION;
  const results = await PermissionsAndroid.requestMultiple([p]);
  bleDiag('permission-result', {apiLevel, results});
  const missing =
    results[p] !== PermissionsAndroid.RESULTS.GRANTED ? [p] : [];
  return { ok: missing.length === 0, missing };
}
