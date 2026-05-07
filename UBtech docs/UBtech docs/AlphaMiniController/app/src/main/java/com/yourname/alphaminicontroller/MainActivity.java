package com.yourname.alphaminicontroller;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.TextView;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.snackbar.Snackbar;
import com.yourname.alphaminicontroller.adapter.DeviceAdapter;
import com.yourname.alphaminicontroller.bluetooth.BluetoothScanner;
import com.yourname.alphaminicontroller.bluetooth.BluetoothService;
import com.yourname.alphaminicontroller.bluetooth.RobotBluetoothManager;
import com.yourname.alphaminicontroller.model.RobotDevice;

import java.util.ArrayList;
import java.util.List;

/**
 * Main screen: Bluetooth device scanner and connection initiator.
 */
public class MainActivity extends AppCompatActivity {

    private static final String TAG = "MainActivity";

    // ── Views ─────────────────────────────────────────────────────────────────
    private TextView tvStatus;
    private View progressScan;
    private TextView tvEmpty;
    private MaterialButton btnScan;
    private MaterialButton btnConnect;
    private RecyclerView recyclerDevices;

    // ── BT components ─────────────────────────────────────────────────────────
    private RobotBluetoothManager btManager;
    private BluetoothScanner scanner;
    private DeviceAdapter deviceAdapter;
    private RobotDevice selectedDevice;

    // ── Permission launcher ───────────────────────────────────────────────────
    private final ActivityResultLauncher<String[]> permissionLauncher =
            registerForActivityResult(new ActivityResultContracts.RequestMultiplePermissions(),
                    result -> {
                        boolean allGranted = !result.containsValue(false);
                        if (allGranted) {
                            startScan();
                        } else {
                            showSnack(getString(R.string.permission_required));
                        }
                    });

    private final ActivityResultLauncher<Intent> enableBtLauncher =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(),
                    result -> {
                        if (btManager.isBluetoothEnabled()) {
                            requestPermissionsAndScan();
                        } else {
                            showSnack(getString(R.string.enable_bluetooth));
                        }
                    });

    // ── LocalBroadcast receiver (for connection state from BluetoothService) ──
    private final BroadcastReceiver stateReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            int state = intent.getIntExtra(BluetoothService.EXTRA_STATE, BluetoothService.STATE_DISCONNECTED);
            updateStatus(state);
            if (state == BluetoothService.STATE_CONNECTED) {
                // Navigate to ControlActivity
                Intent ctrl = new Intent(MainActivity.this, ControlActivity.class);
                if (selectedDevice != null) {
                    ctrl.putExtra(BluetoothService.EXTRA_DEVICE_NAME, selectedDevice.getName());
                }
                startActivity(ctrl);
            }
        }
    };

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        btManager = RobotBluetoothManager.getInstance(this);

        if (!btManager.isBluetoothAvailable()) {
            showSnack(getString(R.string.bt_not_supported));
            return;
        }

        initViews();
        setupRecyclerView();
        setupScanner();
        setupClickListeners();

        // Register for connection state updates from BluetoothService
        LocalBroadcastManager.getInstance(this).registerReceiver(
                stateReceiver, new IntentFilter(BluetoothService.BROADCAST_STATE));
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Reset UI state - user may have returned from ControlActivity
        updateStatus(BluetoothService.STATE_DISCONNECTED);
        btnConnect.setEnabled(selectedDevice != null);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        LocalBroadcastManager.getInstance(this).unregisterReceiver(stateReceiver);
        if (scanner != null) scanner.unregister();
    }

    // ── Init ──────────────────────────────────────────────────────────────────

    private void initViews() {
        tvStatus        = findViewById(R.id.tv_status);
        progressScan    = findViewById(R.id.progress_scan);
        tvEmpty         = findViewById(R.id.tv_empty);
        btnScan         = findViewById(R.id.btn_scan);
        btnConnect      = findViewById(R.id.btn_connect);
        recyclerDevices = findViewById(R.id.recycler_devices);
    }

    private void setupRecyclerView() {
        deviceAdapter = new DeviceAdapter(device -> {
            selectedDevice = device;
            btnConnect.setEnabled(true);
            Log.d(TAG, "Selected: " + device);
        });
        recyclerDevices.setLayoutManager(new LinearLayoutManager(this));
        recyclerDevices.setAdapter(deviceAdapter);
    }

    private void setupScanner() {
        scanner = new BluetoothScanner(this, btManager.getAdapter(), new BluetoothScanner.ScanCallback() {
            @Override
            public void onScanStarted() {
                runOnUiThread(() -> {
                    progressScan.setVisibility(View.VISIBLE);
                    tvEmpty.setVisibility(View.GONE);
                    btnScan.setText(getString(R.string.scanning));
                    btnScan.setEnabled(false);
                });
            }

            @Override
            public void onDeviceFound(RobotDevice device) {
                runOnUiThread(() -> {
                    deviceAdapter.addDevice(device);
                    tvEmpty.setVisibility(View.GONE);
                });
            }

            @Override
            public void onScanFinished() {
                runOnUiThread(() -> {
                    progressScan.setVisibility(View.GONE);
                    btnScan.setText(getString(R.string.scan_devices));
                    btnScan.setEnabled(true);
                    if (deviceAdapter.getItemCount() == 0) {
                        tvEmpty.setVisibility(View.VISIBLE);
                    }
                });
            }
        });
    }

    private void setupClickListeners() {
        btnScan.setOnClickListener(v -> {
            deviceAdapter.clearDevices();
            selectedDevice = null;
            btnConnect.setEnabled(false);
            if (!btManager.isBluetoothEnabled()) {
                enableBtLauncher.launch(new Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE));
            } else {
                requestPermissionsAndScan();
            }
        });

        btnConnect.setOnClickListener(v -> {
            if (selectedDevice == null) return;
            initiateConnection(selectedDevice);
        });
    }

    // ── Scan & Connect ────────────────────────────────────────────────────────

    private void requestPermissionsAndScan() {
        List<String> perms = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (!hasPermission(Manifest.permission.BLUETOOTH_SCAN))
                perms.add(Manifest.permission.BLUETOOTH_SCAN);
            if (!hasPermission(Manifest.permission.BLUETOOTH_CONNECT))
                perms.add(Manifest.permission.BLUETOOTH_CONNECT);
        } else {
            if (!hasPermission(Manifest.permission.ACCESS_FINE_LOCATION))
                perms.add(Manifest.permission.ACCESS_FINE_LOCATION);
        }

        if (perms.isEmpty()) {
            startScan();
        } else {
            permissionLauncher.launch(perms.toArray(new String[0]));
        }
    }

    private void startScan() {
        scanner.startScan();
    }

    private void initiateConnection(RobotDevice device) {
        updateStatus(BluetoothService.STATE_CONNECTING);
        showSnack(getString(R.string.connecting) + " " + device.getName());

        // Start the foreground service with CONNECT action
        Intent intent = new Intent(this, BluetoothService.class);
        intent.setAction(BluetoothService.ACTION_CONNECT);
        intent.putExtra(BluetoothService.EXTRA_DEVICE_MAC,  device.getMacAddress());
        intent.putExtra(BluetoothService.EXTRA_DEVICE_NAME, device.getName());

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
    }

    // ── UI helpers ────────────────────────────────────────────────────────────

    private void updateStatus(int state) {
        switch (state) {
            case BluetoothService.STATE_CONNECTING:
                tvStatus.setText(getString(R.string.connecting));
                tvStatus.setTextColor(getColor(R.color.connecting));
                break;
            case BluetoothService.STATE_CONNECTED:
                tvStatus.setText(getString(R.string.connected));
                tvStatus.setTextColor(getColor(R.color.connected));
                break;
            case BluetoothService.STATE_RECONNECTING:
                tvStatus.setText(getString(R.string.reconnecting));
                tvStatus.setTextColor(getColor(R.color.connecting));
                break;
            default:
                tvStatus.setText(getString(R.string.disconnected));
                tvStatus.setTextColor(0xFFBBDEFB);
                break;
        }
    }

    private void showSnack(String msg) {
        Snackbar.make(findViewById(android.R.id.content), msg, Snackbar.LENGTH_SHORT).show();
    }

    private boolean hasPermission(String permission) {
        return ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED;
    }
}
