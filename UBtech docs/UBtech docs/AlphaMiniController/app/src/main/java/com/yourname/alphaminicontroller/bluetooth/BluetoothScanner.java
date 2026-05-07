package com.yourname.alphaminicontroller.bluetooth;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.os.Build;
import android.util.Log;

import androidx.core.content.ContextCompat;

import com.yourname.alphaminicontroller.model.RobotDevice;

import java.util.ArrayList;
import java.util.List;

/**
 * Manages Bluetooth Classic device discovery.
 * Listens for BluetoothDevice.ACTION_FOUND broadcasts and notifies the caller.
 */
public class BluetoothScanner {

    private static final String TAG = "BluetoothScanner";

    public interface ScanCallback {
        void onDeviceFound(RobotDevice device);
        void onScanFinished();
        void onScanStarted();
    }

    private final Context context;
    private final BluetoothAdapter adapter;
    private final ScanCallback callback;
    private final List<String> foundMacs = new ArrayList<>();
    private boolean isRegistered = false;

    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context ctx, Intent intent) {
            String action = intent.getAction();

            if (BluetoothDevice.ACTION_FOUND.equals(action)) {
                BluetoothDevice device;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    device = intent.getParcelableExtra(
                            BluetoothDevice.EXTRA_DEVICE, BluetoothDevice.class);
                } else {
                    //noinspection deprecation
                    device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
                }
                if (device == null) return;

                String mac = device.getAddress();
                if (foundMacs.contains(mac)) return; // deduplicate
                foundMacs.add(mac);

                String name = "";
                if (hasConnectPermission()) {
                    try { name = device.getName(); } catch (SecurityException ignored) {}
                }
                Log.d(TAG, "Found device: " + name + " [" + mac + "]");
                callback.onDeviceFound(new RobotDevice(name, mac));

            } else if (BluetoothAdapter.ACTION_DISCOVERY_FINISHED.equals(action)) {
                Log.d(TAG, "Discovery finished. Found " + foundMacs.size() + " devices.");
                callback.onScanFinished();
            }
        }
    };

    public BluetoothScanner(Context context, BluetoothAdapter adapter, ScanCallback callback) {
        this.context  = context.getApplicationContext();
        this.adapter  = adapter;
        this.callback = callback;
    }

    /** Start Bluetooth device discovery. */
    public void startScan() {
        if (adapter == null || !adapter.isEnabled()) {
            Log.e(TAG, "Bluetooth adapter not available or disabled");
            return;
        }

        if (!hasScanPermission()) {
            Log.e(TAG, "Missing BLUETOOTH_SCAN / LOCATION permission");
            return;
        }

        foundMacs.clear();

        // Register receiver if not already registered
        if (!isRegistered) {
            IntentFilter filter = new IntentFilter();
            filter.addAction(BluetoothDevice.ACTION_FOUND);
            filter.addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED);
            context.registerReceiver(receiver, filter);
            isRegistered = true;
        }

        try {
            if (adapter.isDiscovering()) {
                adapter.cancelDiscovery();
            }
            adapter.startDiscovery();
            Log.d(TAG, "Discovery started");
            callback.onScanStarted();
        } catch (SecurityException e) {
            Log.e(TAG, "startDiscovery failed: " + e.getMessage());
        }
    }

    /** Stop an ongoing scan and unregister the receiver. */
    public void stopScan() {
        if (adapter != null && hasScanPermission()) {
            try {
                if (adapter.isDiscovering()) adapter.cancelDiscovery();
            } catch (SecurityException ignored) {}
        }
        unregister();
    }

    public void unregister() {
        if (isRegistered) {
            try { context.unregisterReceiver(receiver); } catch (Exception ignored) {}
            isRegistered = false;
        }
    }

    // ── Permission helpers ────────────────────────────────────────────────────

    private boolean hasScanPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return ContextCompat.checkSelfPermission(context,
                    Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED;
        }
        return ContextCompat.checkSelfPermission(context,
                Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private boolean hasConnectPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return ContextCompat.checkSelfPermission(context,
                    Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
        }
        return true;
    }
}
