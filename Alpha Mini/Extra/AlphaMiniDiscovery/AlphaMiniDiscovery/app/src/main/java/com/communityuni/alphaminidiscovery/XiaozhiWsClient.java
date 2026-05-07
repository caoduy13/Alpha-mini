package com.communityuni.alphaminidiscovery;

import android.util.Log;

import org.json.JSONObject;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * WebSocket client tối giản cho Xiaozhi.
 * Gửi text lên server, nhận text/JSON reply.
 */
public class XiaozhiWsClient {
    private static final String TAG = "XiaozhiWsClient";

    public interface Listener {
        void onStatus(String status);
        void onReplyText(String text);
    }

    private final OkHttpClient httpClient;
    private final Listener listener;
    private WebSocket ws;
    private String wsUrl;

    public XiaozhiWsClient(String wsUrl, Listener listener) {
        this.wsUrl = wsUrl;
        this.listener = listener;
        this.httpClient = new OkHttpClient.Builder().build();
    }

    public void setWsUrl(String wsUrl) {
        this.wsUrl = wsUrl;
    }

    public void connect() {
        if (ws != null) return;
        listener.onStatus("Đang kết nối Xiaozhi...");
        Request req = new Request.Builder().url(wsUrl).build();
        ws = httpClient.newWebSocket(req, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket webSocket, Response response) {
                Log.i(TAG, "WS open");
                listener.onStatus("Đã kết nối Xiaozhi");
            }

            @Override
            public void onMessage(WebSocket webSocket, String text) {
                Log.d(TAG, "WS message: " + text);
                listener.onReplyText(extractReplyText(text));
            }

            @Override
            public void onClosing(WebSocket webSocket, int code, String reason) {
                Log.i(TAG, "WS closing: " + code + " " + reason);
                listener.onStatus("Xiaozhi đang đóng kết nối...");
            }

            @Override
            public void onClosed(WebSocket webSocket, int code, String reason) {
                Log.i(TAG, "WS closed: " + code + " " + reason);
                ws = null;
                listener.onStatus("Xiaozhi đã ngắt kết nối");
            }

            @Override
            public void onFailure(WebSocket webSocket, Throwable t, Response response) {
                Log.e(TAG, "WS failure", t);
                ws = null;
                listener.onStatus("Lỗi WS Xiaozhi: " + t.getMessage());
            }
        });
    }

    public void disconnect() {
        if (ws != null) {
            ws.close(1000, "bye");
            ws = null;
        }
    }

    public boolean isConnected() {
        return ws != null;
    }

    public void sendUserText(String userText) {
        if (ws == null) {
            connect();
        }
        if (ws == null) return;

        // Payload tối giản. Nếu server Xiaozhi yêu cầu format khác, sẽ chỉnh tiếp.
        JSONObject payload = new JSONObject();
        try {
            payload.put("type", "text");
            payload.put("text", userText);
        } catch (Exception ignored) { }

        ws.send(payload.toString());
    }

    private String extractReplyText(String raw) {
        try {
            JSONObject obj = new JSONObject(raw);
            // ưu tiên các field phổ biến
            if (obj.has("text")) return obj.optString("text");
            if (obj.has("reply")) return obj.optString("reply");
            if (obj.has("message")) return obj.optString("message");
        } catch (Exception ignored) {
        }
        return raw;
    }
}

