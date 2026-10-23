import { PermissionsAndroid, Platform } from 'react-native';

export async function requestBlePermissions(): Promise<{
  ok: boolean;
  missing: string[];
}> {
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
    const missing = ps.filter(
      p => results[p] !== PermissionsAndroid.RESULTS.GRANTED,
    );
    return { ok: missing.length === 0, missing };
  }

  const p = PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION;
  const results = await PermissionsAndroid.requestMultiple([p]);
  const missing =
    results[p] !== PermissionsAndroid.RESULTS.GRANTED ? [p] : [];
  return { ok: missing.length === 0, missing };
}
