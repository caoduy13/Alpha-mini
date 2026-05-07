package com.yourname.alphaminicontroller.bluetooth;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;

import com.yourname.alphaminicontroller.MainActivity;
import com.yourname.alphaminicontroller.R;
import com.yourname.alphaminicontroller.utils.Logger;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.UUID;

/**
 * Foreground Service that manages the Bluetooth RFCOMM (SPP) connection with
 * the Alpha Mini robot. Runs socket I/O in dedicated background threads and
 * communicates state / data back to Activities via LocalBroadcastManager.
 *
 * Intent actions (startService):
 *   ACTION_CONNECT     – extra: EXTRA_DEVICE_MAC, EXTRA_DEVICE_NAME
 *   ACTION_SEND        – extra: EXTRA_COMMAND (JSON string)
 *   ACTION_DISCONNECT
 *
 * LocalBroadcast actions (sent by the service):
 *   BROADCAST_STATE    – extra: EXTRA_STATE (STATE_*)
 *   BROADCAST_DATA     – extra: EXTRA_DATA (raw string from robot)
 *   BROADCAST_LOG      – extra: EXTRA_LOG  (formatted log line)
 */
public class BluetoothService extends Service {

    private static final String TAG = "BluetoothService";

    // ── SPP UUID ──────────────────────────────────────────────────────────────
    private static final UUID SPP_UUID =
            UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    // Connection timeout: kill connect() after this many ms
    private static final int CONNECT_TIMEOUT_MS = 10_000;

    // ── Intent actions ────────────────────────────────────────────────────────
    public static final String ACTION_CONNECT    = "com.alphamini.ACTION_CONNECT";
    public static final String ACTION_SEND       = "com.alphamini.ACTION_SEND";
    public static final String ACTION_DISCONNECT = "com.alphamini.ACTION_DISCONNECT";

    // ── Broadcast constants ───────────────────────────────────────────────────
    public static final String BROADCAST_STATE = "com.alphamini.STATE";
    public static final String BROADCAST_DATA  = "com.alphamini.DATA";
    public static final String BROADCAST_LOG   = "com.alphamini.LOG";

    public static final String EXTRA_STATE      = "state";
    public static final String EXTRA_DATA       = "data";
    public static final String EXTRA_LOG        = "log";
    public static final String EXTRA_DEVICE_MAC  = "device_mac";
    public static final String EXTRA_DEVICE_NAME = "device_name";
    public static final String EXTRA_COMMAND    = "command";

    // ── Connection states ─────────────────────────────────────────────────────
    public static final int STATE_DISCONNECTED = 0;
    public static final int STATE_CONNECTING   = 1;
    public static final int STATE_CONNECTED    = 2;
    public static final int STATE_RECONNECTING = 3;

    // ── Reconnect config ──────────────────────────────────────────────────────
    private static final int RECONNECT_DELAY_MS = 5000;
    private static final int MAX_RECONNECT_ATTEMPTS = 5;

    // ── Notification ──────────────────────────────────────────────────────────
    private static final String NOTIF_CHANNEL_ID = "AlphaMiniChannel";
    private static final int    NOTIF_ID         = 1001;

    // ── State ─────────────────────────────────────────────────────────────────
    private BluetoothSocket socket;
    private InputStream  inputStream;
    private OutputStream outputStream;
    private Thread readThread;
    private Thread connectThread;
    private int currentState = STATE_DISCONNECTED;
    private String pendingMac;
    private String pendingName;
    private int reconnectAttempts = 0;
    private boolean autoReconnect = true;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    // ── Service lifecycle ─────────────────────────────────────────────────────

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        startForeground(NOTIF_ID, buildNotification("Waiting for connection…"));
        Logger.d("BluetoothService created");
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_STICKY;

        String action = intent.getAction();
        Logger.d("onStartCommand: " + action);

        if (ACTION_CONNECT.equals(action)) {
            pendingMac  = intent.getStringExtra(EXTRA_DEVICE_MAC);
            pendingName = intent.getStringExtra(EXTRA_DEVICE_NAME);
            autoReconnect = true;
            reconnectAttempts = 0;
            connectToDevice(pendingMac, pendingName);

        } else if (ACTION_SEND.equals(action)) {
            String command = intent.getStringExtra(EXTRA_COMMAND);
            if (command != null) sendCommand(command);

        } else if (ACTION_DISCONNECT.equals(action)) {
            autoReconnect = false;
            disconnect();
        }

        return START_STICKY;
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public void onDestroy() {
        autoReconnect = false;
        disconnect();
        Logger.d("BluetoothService destroyed");
        super.onDestroy();
    }

    // ── Connection ────────────────────────────────────────────────────────────

    private void connectToDevice(final String mac, final String name) {
        if (mac == null) {
            Logger.e("connectToDevice: null MAC address");
            return;
        }

        setState(STATE_CONNECTING);
        broadcastLog(Logger.info("Connecting to " + name + " [" + mac + "]…"));

        // Cancel any existing connect thread
        if (connectThread != null && connectThread.isAlive()) {
            connectThread.interrupt();
        }
        closeSocket();

        connectThread = new Thread(() -> {
            BluetoothAdapter adapter = RobotBluetoothManager.getInstance(this).getAdapter();
            if (adapter == null) {
                mainHandler.post(() -> onConnectionFailed("Bluetooth not available"));
                return;
            }

            if (!hasConnectPermission()) {
                mainHandler.post(() -> onConnectionFailed("Missing BLUETOOTH_CONNECT permission"));
                return;
            }

            try {
                // Cancel discovery to speed up connection
                try { adapter.cancelDiscovery(); } catch (SecurityException ignored) {}

                BluetoothDevice device = adapter.getRemoteDevice(mac);
                BluetoothSocket btSocket = null;

                // Strategy 1: Insecure RFCOMM (no pairing required, works on many embedded devices)
                broadcastLog(Logger.info("Trying insecure RFCOMM (SPP)…"));
                try {
                    btSocket = device.createInsecureRfcommSocketToServiceRecord(SPP_UUID);
                    connectWithTimeout(btSocket);
                    Logger.i("Connected via insecure RFCOMM");
                } catch (Exception e1) {
                    Logger.e("Insecure RFCOMM failed: " + e1.getMessage());
                    safeClose(btSocket);
                    btSocket = null;

                    // Strategy 2: Secure RFCOMM with SPP UUID
                    broadcastLog(Logger.info("Trying secure RFCOMM (SPP)…"));
                    try {
                        btSocket = device.createRfcommSocketToServiceRecord(SPP_UUID);
                        connectWithTimeout(btSocket);
                        Logger.i("Connected via secure RFCOMM");
                    } catch (Exception e2) {
                        Logger.e("Secure RFCOMM failed: " + e2.getMessage());
                        safeClose(btSocket);
                        btSocket = null;

                        // Strategy 3: Reflection – connect on raw RFCOMM channel 1
                        broadcastLog(Logger.info("Trying raw channel 1 (reflection)…"));
                        try {
                            java.lang.reflect.Method m = device.getClass()
                                    .getMethod("createRfcommSocket", int.class);
                            btSocket = (BluetoothSocket) m.invoke(device, 1);
                            connectWithTimeout(btSocket);
                            Logger.i("Connected via raw channel 1");
                        } catch (Exception e3) {
                            Logger.e("Raw channel failed: " + e3.getMessage());
                            safeClose(btSocket);
                            btSocket = null;
                        }
                    }
                }

                if (btSocket == null || !btSocket.isConnected()) {
                    mainHandler.post(() -> onConnectionFailed(
                            "All connection methods failed. Make sure robot Bluetooth is on and not paired to another device."));
                    return;
                }

                socket       = btSocket;
                inputStream  = btSocket.getInputStream();
                outputStream = btSocket.getOutputStream();

                mainHandler.post(() -> onConnected(name, mac));

            } catch (SecurityException e) {
                Logger.e("Connect SecurityException: " + e.getMessage());
                mainHandler.post(() -> onConnectionFailed("Permission denied: " + e.getMessage()));
            } catch (Exception e) {
                Logger.e("Connect error: " + e.getMessage());
                mainHandler.post(() -> onConnectionFailed(e.getMessage()));
            }
        }, "BT-Connect");
        connectThread.start();
    }

    /**
     * Calls socket.connect() but enforces a timeout by closing the socket
     * from a watchdog thread if it takes too long.
     */
    private void connectWithTimeout(BluetoothSocket btSocket) throws IOException {
        // Watchdog: close socket after CONNECT_TIMEOUT_MS to unblock connect()
        Thread watchdog = new Thread(() -> {
            try {
                Thread.sleep(CONNECT_TIMEOUT_MS);
                Logger.e("Connection timeout after " + CONNECT_TIMEOUT_MS + "ms – closing socket");
                safeClose(btSocket);
            } catch (InterruptedException ignored) {}
        }, "BT-Watchdog");
        watchdog.setDaemon(true);
        watchdog.start();

        try {
            btSocket.connect(); // blocks until connected or socket closed
        } finally {
            watchdog.interrupt(); // stop watchdog if connect() returned
        }
    }

    private void safeClose(BluetoothSocket s) {
        if (s != null) { try { s.close(); } catch (IOException ignored) {} }
    }

    private void onConnected(String name, String mac) {
        Logger.i("Connected to " + name);
        reconnectAttempts = 0;
        setState(STATE_CONNECTED);
        updateNotification("Connected to " + name);
        broadcastLog(Logger.info("Connected to " + name + " [" + mac + "]"));

        // Save last device
        RobotBluetoothManager.getInstance(this).saveLastDevice(mac, name);

        // Start reading from robot
        startReadThread();
    }

    private void onConnectionFailed(String reason) {
        Logger.e("Connection failed: " + reason);
        broadcastLog(Logger.error("Connection failed: " + reason));
        scheduleReconnect();
    }

    private void onConnectionLost(String reason) {
        Logger.e("Connection lost: " + reason);
        broadcastLog(Logger.error("Connection lost: " + reason));
        scheduleReconnect();
    }

    private void scheduleReconnect() {
        if (!autoReconnect || pendingMac == null) {
            setState(STATE_DISCONNECTED);
            updateNotification("Disconnected");
            return;
        }
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            Logger.e("Max reconnect attempts reached");
            broadcastLog(Logger.error("Max reconnect attempts reached. Giving up."));
            setState(STATE_DISCONNECTED);
            updateNotification("Connection failed");
            return;
        }
        reconnectAttempts++;
        setState(STATE_RECONNECTING);
        broadcastLog(Logger.info("Reconnecting in 5s… (attempt " + reconnectAttempts + "/" + MAX_RECONNECT_ATTEMPTS + ")"));
        updateNotification("Reconnecting…");
        mainHandler.postDelayed(() -> connectToDevice(pendingMac, pendingName), RECONNECT_DELAY_MS);
    }

    // ── Read thread ───────────────────────────────────────────────────────────

    private void startReadThread() {
        if (readThread != null && readThread.isAlive()) {
            readThread.interrupt();
        }

        readThread = new Thread(() -> {
            byte[] buffer = new byte[1024];
            StringBuilder messageBuffer = new StringBuilder();

            Logger.d("Read thread started");

            while (!Thread.currentThread().isInterrupted()) {
                try {
                    int bytes = inputStream.read(buffer);
                    if (bytes <= 0) continue;

                    String chunk = new String(buffer, 0, bytes);
                    messageBuffer.append(chunk);

                    // Process complete newline-delimited messages
                    int newlineIdx;
                    while ((newlineIdx = messageBuffer.indexOf("\n")) >= 0) {
                        String msg = messageBuffer.substring(0, newlineIdx).trim();
                        messageBuffer.delete(0, newlineIdx + 1);
                        if (!msg.isEmpty()) {
                            Logger.d("Received: " + msg);
                            broadcastData(msg);
                            broadcastLog(Logger.received(msg));
                        }
                    }

                } catch (IOException e) {
                    if (!Thread.currentThread().isInterrupted()) {
                        Logger.e("Read error: " + e.getMessage());
                        mainHandler.post(() -> onConnectionLost(e.getMessage()));
                    }
                    break;
                }
            }
            Logger.d("Read thread finished");
        }, "BT-Read");
        readThread.setDaemon(true);
        readThread.start();
    }

    // ── Write ─────────────────────────────────────────────────────────────────

    private void sendCommand(final String json) {
        if (currentState != STATE_CONNECTED || outputStream == null) {
            broadcastLog(Logger.error("Not connected – cannot send: " + json.trim()));
            return;
        }

        new Thread(() -> {
            try {
                outputStream.write(json.getBytes("UTF-8"));
                outputStream.flush();
                Logger.d("Sent: " + json.trim());
                mainHandler.post(() -> broadcastLog(Logger.sent(json.trim())));
            } catch (IOException e) {
                Logger.e("Write error: " + e.getMessage());
                mainHandler.post(() -> {
                    broadcastLog(Logger.error("Send failed: " + e.getMessage()));
                    onConnectionLost(e.getMessage());
                });
            }
        }, "BT-Write").start();
    }

    // ── Disconnect ────────────────────────────────────────────────────────────

    private void disconnect() {
        if (readThread != null) { readThread.interrupt(); readThread = null; }
        if (connectThread != null) { connectThread.interrupt(); connectThread = null; }
        closeSocket();
        setState(STATE_DISCONNECTED);
        updateNotification("Disconnected");
        broadcastLog(Logger.info("Disconnected"));
    }

    private void closeSocket() {
        try { if (inputStream != null)  inputStream.close();  } catch (IOException ignored) {}
        try { if (outputStream != null) outputStream.close(); } catch (IOException ignored) {}
        try { if (socket != null)       socket.close();       } catch (IOException ignored) {}
        socket = null;
        outputStream = null;
        inputStream = null;
    }

    // ── Broadcast helpers ─────────────────────────────────────────────────────

    private void setState(int state) {
        currentState = state;
        Intent intent = new Intent(BROADCAST_STATE);
        intent.putExtra(EXTRA_STATE, state);
        LocalBroadcastManager.getInstance(this).sendBroadcast(intent);
    }

    private void broadcastData(String data) {
        Intent intent = new Intent(BROADCAST_DATA);
        intent.putExtra(EXTRA_DATA, data);
        LocalBroadcastManager.getInstance(this).sendBroadcast(intent);
    }

    private void broadcastLog(String logLine) {
        Intent intent = new Intent(BROADCAST_LOG);
        intent.putExtra(EXTRA_LOG, logLine);
        LocalBroadcastManager.getInstance(this).sendBroadcast(intent);
    }

    // ── Notification ──────────────────────────────────────────────────────────

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    NOTIF_CHANNEL_ID,
                    getString(R.string.notif_channel_name),
                    NotificationManager.IMPORTANCE_LOW);
            channel.setDescription(getString(R.string.notif_channel_desc));
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        }
    }

    private Notification buildNotification(String text) {
        Intent launchIntent = new Intent(this, MainActivity.class);
        launchIntent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        int flags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                ? PendingIntent.FLAG_IMMUTABLE : 0;
        PendingIntent pi = PendingIntent.getActivity(this, 0, launchIntent, flags);

        return new NotificationCompat.Builder(this, NOTIF_CHANNEL_ID)
                .setContentTitle(getString(R.string.notif_title))
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_menu_share)
                .setContentIntent(pi)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build();
    }

    private void updateNotification(String text) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm != null) nm.notify(NOTIF_ID, buildNotification(text));
    }

    // ── Permission helper ─────────────────────────────────────────────────────

    private boolean hasConnectPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return ContextCompat.checkSelfPermission(this,
                    Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
        }
        return true;
    }
}
