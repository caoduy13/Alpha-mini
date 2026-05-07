package com.yourname.alphaminicontroller;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Bundle;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.snackbar.Snackbar;
import com.yourname.alphaminicontroller.bluetooth.BluetoothService;
import com.yourname.alphaminicontroller.utils.CommandBuilder;
import com.yourname.alphaminicontroller.utils.Logger;

/**
 * Robot control screen.
 * Provides buttons for all robot actions, TTS input, and a live command log.
 */
public class ControlActivity extends AppCompatActivity {

    private static final String TAG = "ControlActivity";

    // ── Views ─────────────────────────────────────────────────────────────────
    private TextView tvConnectionStatus;
    private TextView tvDeviceName;
    private TextView tvLog;
    private ScrollView scrollLog;
    private EditText etSpeakText;

    // ── State ─────────────────────────────────────────────────────────────────
    private int connectionState = BluetoothService.STATE_CONNECTED;
    private final StringBuilder logBuffer = new StringBuilder();

    // ── LocalBroadcast receivers ──────────────────────────────────────────────

    private final BroadcastReceiver stateReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context ctx, Intent intent) {
            int state = intent.getIntExtra(BluetoothService.EXTRA_STATE,
                    BluetoothService.STATE_DISCONNECTED);
            connectionState = state;
            updateConnectionStatus(state);
            if (state == BluetoothService.STATE_DISCONNECTED) {
                showSnack("Connection lost. Returning…");
                finish();
            }
        }
    };

    private final BroadcastReceiver logReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context ctx, Intent intent) {
            String line = intent.getStringExtra(BluetoothService.EXTRA_LOG);
            if (line != null) appendLog(line);
        }
    };

    private final BroadcastReceiver dataReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context ctx, Intent intent) {
            String data = intent.getStringExtra(BluetoothService.EXTRA_DATA);
            if (data != null) handleRobotData(data);
        }
    };

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_control);

        initViews();
        setupActionButtons();
        setupTtsSection();
        registerReceivers();

        // Show device name from intent
        String deviceName = getIntent().getStringExtra(BluetoothService.EXTRA_DEVICE_NAME);
        if (deviceName != null) tvDeviceName.setText(deviceName);

        appendLog(Logger.info("Control screen opened. Robot is connected."));

        // Optionally query battery on connect
        sendCommand(CommandBuilder.getBattery());
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        LocalBroadcastManager.getInstance(this).unregisterReceiver(stateReceiver);
        LocalBroadcastManager.getInstance(this).unregisterReceiver(logReceiver);
        LocalBroadcastManager.getInstance(this).unregisterReceiver(dataReceiver);
    }

    // ── Init ──────────────────────────────────────────────────────────────────

    private void initViews() {
        tvConnectionStatus = findViewById(R.id.tv_connection_status);
        tvDeviceName       = findViewById(R.id.tv_device_name);
        tvLog              = findViewById(R.id.tv_log);
        scrollLog          = findViewById(R.id.scroll_log);
        etSpeakText        = findViewById(R.id.et_speak_text);
    }

    private void setupActionButtons() {
        findViewById(R.id.btn_wave).setOnClickListener(v ->
                sendCommand(CommandBuilder.wave()));

        findViewById(R.id.btn_dance).setOnClickListener(v ->
                sendCommand(CommandBuilder.dance()));

        findViewById(R.id.btn_forward).setOnClickListener(v ->
                sendCommand(CommandBuilder.forward()));

        findViewById(R.id.btn_backward).setOnClickListener(v ->
                sendCommand(CommandBuilder.backward()));

        findViewById(R.id.btn_turn_left).setOnClickListener(v ->
                sendCommand(CommandBuilder.turnLeft()));

        findViewById(R.id.btn_turn_right).setOnClickListener(v ->
                sendCommand(CommandBuilder.turnRight()));

        findViewById(R.id.btn_sit).setOnClickListener(v ->
                sendCommand(CommandBuilder.sitDown()));

        findViewById(R.id.btn_stand).setOnClickListener(v ->
                sendCommand(CommandBuilder.standUp()));

        findViewById(R.id.btn_stop).setOnClickListener(v ->
                sendCommand(CommandBuilder.stop()));

        // WiFi config
        findViewById(R.id.btn_wifi_config).setOnClickListener(v ->
                startActivity(new Intent(this, WifiConfigActivity.class)));

        // Disconnect
        ((MaterialButton) findViewById(R.id.btn_disconnect)).setOnClickListener(v -> {
            sendServiceAction(BluetoothService.ACTION_DISCONNECT);
            finish();
        });

        // Clear log
        ((MaterialButton) findViewById(R.id.btn_clear_log)).setOnClickListener(v -> {
            logBuffer.setLength(0);
            tvLog.setText("");
        });
    }

    private void setupTtsSection() {
        ((MaterialButton) findViewById(R.id.btn_speak)).setOnClickListener(v -> {
            String text = etSpeakText.getText().toString().trim();
            if (text.isEmpty()) {
                showSnack("Please enter text for the robot to speak");
                return;
            }
            sendCommand(CommandBuilder.speak(text));
            // Hide keyboard
            InputMethodManager imm = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            if (imm != null) imm.hideSoftInputFromWindow(etSpeakText.getWindowToken(), 0);
        });
    }

    private void registerReceivers() {
        LocalBroadcastManager lbm = LocalBroadcastManager.getInstance(this);
        lbm.registerReceiver(stateReceiver, new IntentFilter(BluetoothService.BROADCAST_STATE));
        lbm.registerReceiver(logReceiver,   new IntentFilter(BluetoothService.BROADCAST_LOG));
        lbm.registerReceiver(dataReceiver,  new IntentFilter(BluetoothService.BROADCAST_DATA));
    }

    // ── Command sending ───────────────────────────────────────────────────────

    private void sendCommand(String json) {
        if (connectionState != BluetoothService.STATE_CONNECTED) {
            showSnack("Not connected to robot");
            return;
        }
        Intent intent = new Intent(this, BluetoothService.class);
        intent.setAction(BluetoothService.ACTION_SEND);
        intent.putExtra(BluetoothService.EXTRA_COMMAND, json);
        startService(intent);
    }

    private void sendServiceAction(String action) {
        Intent intent = new Intent(this, BluetoothService.class);
        intent.setAction(action);
        startService(intent);
    }

    // ── Data handling ─────────────────────────────────────────────────────────

    private void handleRobotData(String json) {
        // Parse battery level if present
        try {
            if (json.contains("battery")) {
                // Simple string scan — replace with Gson for full parsing
                int idx = json.indexOf("battery");
                String sub = json.substring(idx);
                int numStart = sub.indexOf(':') + 1;
                int numEnd = sub.indexOf('}');
                if (numEnd < 0) numEnd = sub.length();
                String level = sub.substring(numStart, numEnd).replaceAll("[^0-9]", "").trim();
                if (!level.isEmpty()) {
                    runOnUiThread(() -> tvConnectionStatus.setText("● Connected  🔋 " + level + "%"));
                }
            }
        } catch (Exception ignored) {}
    }

    // ── UI helpers ────────────────────────────────────────────────────────────

    private void updateConnectionStatus(int state) {
        switch (state) {
            case BluetoothService.STATE_CONNECTED:
                tvConnectionStatus.setText("● Connected");
                tvConnectionStatus.setTextColor(getColor(R.color.connected));
                break;
            case BluetoothService.STATE_RECONNECTING:
                tvConnectionStatus.setText("↻ Reconnecting…");
                tvConnectionStatus.setTextColor(getColor(R.color.connecting));
                break;
            default:
                tvConnectionStatus.setText("✕ Disconnected");
                tvConnectionStatus.setTextColor(getColor(R.color.disconnected));
                break;
        }
    }

    private void appendLog(String line) {
        runOnUiThread(() -> {
            logBuffer.append(line).append('\n');
            tvLog.setText(logBuffer.toString());
            // Auto-scroll to bottom
            scrollLog.post(() -> scrollLog.fullScroll(ScrollView.FOCUS_DOWN));
        });
    }

    private void showSnack(String msg) {
        Snackbar.make(findViewById(android.R.id.content), msg, Snackbar.LENGTH_SHORT).show();
    }
}
