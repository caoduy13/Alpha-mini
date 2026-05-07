package com.communityuni.alphaminidiscovery.utils;

import android.content.Context;
import android.net.wifi.WifiManager;
import android.text.format.Formatter;

import com.communityuni.alphaminidiscovery.model.RobotStatus;
import com.communityuni.alphaminidiscovery.network.RobotController;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * NetworkScanner: auto-discover robot trong subnet Wi‑Fi hiện tại.
 *
 * Logic:
 * - Lấy IP local (ví dụ 192.168.1.123)
 * - Quét dải 192.168.1.1..254, gọi action=status tới port 8080
 * - Nếu máy nào trả JSON hợp lệ (có session_active) => coi là robot
 */
public class NetworkScanner {

    public interface DiscoveryListener {
        void onFound(String ip);
        void onNotFound();
    }

    private final Context appCtx;
    private final RobotController controller = new RobotController();

    public NetworkScanner(Context ctx) {
        this.appCtx = ctx.getApplicationContext();
    }

    public void discoverRobotIp(final DiscoveryListener listener) {
        final String localIp = getLocalWifiIp();
        if (localIp == null || localIp.trim().isEmpty()) {
            if (listener != null) listener.onNotFound();
            return;
        }

        final String prefix = localIp.substring(0, localIp.lastIndexOf('.') + 1);
        final ExecutorService pool = Executors.newFixedThreadPool(32);
        final AtomicBoolean done = new AtomicBoolean(false);
        final AtomicBoolean any = new AtomicBoolean(false);

        for (int i = 1; i <= 254; i++) {
            final String ip = prefix + i;
            pool.submit(new Runnable() {
                @Override
                public void run() {
                    if (done.get()) return;
                    controller.sendCommand(ip, "status", new RobotController.Listener() {
                        @Override
                        public void onSuccess(RobotStatus status) {
                            if (done.compareAndSet(false, true)) {
                                any.set(true);
                                if (listener != null) listener.onFound(ip);
                                pool.shutdownNow();
                            }
                        }

                        @Override
                        public void onError(String message) {
                            // ignore (đa phần IP sẽ fail timeout)
                        }
                    });
                }
            });
        }

        // Watcher: đợi một khoảng rồi kết luận không tìm thấy
        Executors.newSingleThreadExecutor().submit(new Runnable() {
            @Override
            public void run() {
                try {
                    Thread.sleep(7000);
                } catch (InterruptedException ignored) {
                }
                if (done.compareAndSet(false, true)) {
                    pool.shutdownNow();
                    if (!any.get() && listener != null) listener.onNotFound();
                }
            }
        });
    }

    private String getLocalWifiIp() {
        try {
            WifiManager wm = (WifiManager) appCtx.getSystemService(Context.WIFI_SERVICE);
            if (wm == null) return null;
            int ip = wm.getConnectionInfo() != null ? wm.getConnectionInfo().getIpAddress() : 0;
            if (ip == 0) return null;
            return Formatter.formatIpAddress(ip);
        } catch (Throwable t) {
            return null;
        }
    }
}

