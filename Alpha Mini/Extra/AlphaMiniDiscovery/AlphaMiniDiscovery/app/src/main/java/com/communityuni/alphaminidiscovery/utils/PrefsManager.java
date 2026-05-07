package com.communityuni.alphaminidiscovery.utils;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * PrefsManager: lưu cấu hình app (IP robot, auto-reconnect, ...).
 */
public class PrefsManager {

    private static final String PREFS = "alphamind_prefs";
    private static final String KEY_IP = "robot_ip";
    private static final String KEY_AUTO_RECONNECT = "auto_reconnect";
    private static final String KEY_SHOW_EMO_ANIM = "show_emotion_anim";
    private static final String KEY_MUTED = "muted";

    private final SharedPreferences sp;

    public PrefsManager(Context ctx) {
        sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public String getRobotIp() {
        return sp.getString(KEY_IP, "");
    }

    public void setRobotIp(String ip) {
        sp.edit().putString(KEY_IP, ip == null ? "" : ip.trim()).apply();
    }

    public boolean isAutoReconnect() {
        return sp.getBoolean(KEY_AUTO_RECONNECT, true);
    }

    public void setAutoReconnect(boolean v) {
        sp.edit().putBoolean(KEY_AUTO_RECONNECT, v).apply();
    }

    public boolean isShowEmotionAnim() {
        return sp.getBoolean(KEY_SHOW_EMO_ANIM, true);
    }

    public void setShowEmotionAnim(boolean v) {
        sp.edit().putBoolean(KEY_SHOW_EMO_ANIM, v).apply();
    }

    public boolean isMuted() {
        return sp.getBoolean(KEY_MUTED, false);
    }

    public void setMuted(boolean v) {
        sp.edit().putBoolean(KEY_MUTED, v).apply();
    }
}

