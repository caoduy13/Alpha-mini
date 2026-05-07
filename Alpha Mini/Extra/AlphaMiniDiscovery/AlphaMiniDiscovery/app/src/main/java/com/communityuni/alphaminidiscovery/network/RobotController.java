package com.communityuni.alphaminidiscovery.network;

import androidx.annotation.NonNull;

import com.communityuni.alphaminidiscovery.model.RobotStatus;
import com.google.gson.Gson;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/**
 * RobotController: gửi HTTP command tới robot.
 *
 * POST http://{robot_ip}:8080/command
 * Body JSON: {"action":"start_chat" | "stop_chat" | "status"}
 */
public class RobotController {

    public interface Listener {
        void onSuccess(RobotStatus status);
        void onError(String message);
    }

    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient client;
    private final Gson gson = new Gson();

    public RobotController() {
        client = new OkHttpClient.Builder()
                // Timeout trước đây quá ngắn, dễ làm UI nhảy Offline khi Wi‑Fi chập chờn.
                .connectTimeout(3, TimeUnit.SECONDS)
                .readTimeout(5, TimeUnit.SECONDS)
                .writeTimeout(5, TimeUnit.SECONDS)
                .build();
    }

    public void sendCommand(String robotIp, String action, String text, final Listener cb) {
        if (cb == null) return;
        if (robotIp == null || robotIp.trim().isEmpty()) {
            cb.onError("missing ip");
            return;
        }

        String url = "http://" + robotIp.trim() + ":8080/command";

        Map<String, String> payload = new HashMap<>();
        payload.put("action", action == null ? "" : action);
        if (text != null && text.trim().length() > 0) {
            payload.put("text", text.trim());
        }
        String json = gson.toJson(payload);

        RequestBody body = RequestBody.create(json, JSON);
        Request request = new Request.Builder()
                .url(url)
                .post(body)
                .build();

        client.newCall(request).enqueue(new okhttp3.Callback() {
            @Override
            public void onFailure(@NonNull Call call, @NonNull IOException e) {
                cb.onError(e.getMessage() == null ? "network error" : e.getMessage());
            }

            @Override
            public void onResponse(@NonNull Call call, @NonNull Response response) throws IOException {
                String raw = response.body() != null ? response.body().string() : "";
                if (!response.isSuccessful()) {
                    cb.onError("http " + response.code());
                    return;
                }
                try {
                    RobotStatus status = gson.fromJson(raw, RobotStatus.class);
                    if (status == null) {
                        cb.onError("bad json");
                    } else {
                        cb.onSuccess(status);
                    }
                } catch (Throwable t) {
                    cb.onError("parse error");
                }
            }
        });
    }

    public void sendCommand(String robotIp, String action, final Listener cb) {
        sendCommand(robotIp, action, null, cb);
    }
}

