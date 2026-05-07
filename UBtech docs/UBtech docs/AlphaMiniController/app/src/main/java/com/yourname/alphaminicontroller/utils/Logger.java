package com.yourname.alphaminicontroller.utils;

import android.util.Log;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Simple logger that formats timestamped log entries.
 * Used to display sent commands and received responses in the UI.
 */
public class Logger {

    private static final String TAG = "AlphaMini";
    private static final SimpleDateFormat TIME_FORMAT =
            new SimpleDateFormat("HH:mm:ss", Locale.getDefault());

    /** Format a SENT command entry. */
    public static String sent(String message) {
        return timestamp() + " ▶ SEND: " + message;
    }

    /** Format a RECEIVED data entry. */
    public static String received(String message) {
        return timestamp() + " ◀ RECV: " + message;
    }

    /** Format an INFO entry. */
    public static String info(String message) {
        return timestamp() + " ℹ " + message;
    }

    /** Format an ERROR entry. */
    public static String error(String message) {
        return timestamp() + " ✖ ERROR: " + message;
    }

    private static String timestamp() {
        return "[" + TIME_FORMAT.format(new Date()) + "]";
    }

    // Android logcat helpers
    public static void d(String message) { Log.d(TAG, message); }
    public static void e(String message) { Log.e(TAG, message); }
    public static void i(String message) { Log.i(TAG, message); }
}
