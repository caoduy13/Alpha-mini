package com.yourname.alphaminicontroller.bluetooth;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

/**
 * Singleton that provides access to the BluetoothAdapter and persists
 * the last-connected device (MAC address) in SharedPreferences.
 *
 * Named RobotBluetoothManager to avoid collision with android.bluetooth.BluetoothManager.
 */
public class RobotBluetoothManager {

    private static final String TAG  = "RobotBtManager";
    private static final String PREFS_NAME  = "AlphaMiniPrefs";
    private static final String KEY_LAST_MAC  = "last_device_mac";
    private static final String KEY_LAST_NAME = "last_device_name";

    private static RobotBluetoothManager instance;

    private final BluetoothAdapter bluetoothAdapter;
    private final SharedPreferences prefs;

    private RobotBluetoothManager(Context context) {
        BluetoothManager systemBtManager =
                (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);
        bluetoothAdapter = (systemBtManager != null) ? systemBtManager.getAdapter() : null;
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    public static synchronized RobotBluetoothManager getInstance(Context context) {
        if (instance == null) {
            instance = new RobotBluetoothManager(context.getApplicationContext());
        }
        return instance;
    }

    public BluetoothAdapter getAdapter() { return bluetoothAdapter; }

    public boolean isBluetoothAvailable() { return bluetoothAdapter != null; }

    public boolean isBluetoothEnabled() {
        return bluetoothAdapter != null && bluetoothAdapter.isEnabled();
    }

    // ── Persistent last-device storage ────────────────────────────────────────

    public void saveLastDevice(String mac, String name) {
        prefs.edit()
                .putString(KEY_LAST_MAC, mac)
                .putString(KEY_LAST_NAME, name)
                .apply();
        Log.d(TAG, "Saved last device: " + name + " [" + mac + "]");
    }

    public String getLastDeviceMac()  { return prefs.getString(KEY_LAST_MAC, null); }
    public String getLastDeviceName() { return prefs.getString(KEY_LAST_NAME, null); }

    public boolean hasLastDevice() { return getLastDeviceMac() != null; }

    public void clearLastDevice() {
        prefs.edit().remove(KEY_LAST_MAC).remove(KEY_LAST_NAME).apply();
    }
}
