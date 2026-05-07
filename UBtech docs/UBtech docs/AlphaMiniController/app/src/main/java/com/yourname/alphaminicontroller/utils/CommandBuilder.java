package com.yourname.alphaminicontroller.utils;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.yourname.alphaminicontroller.model.RobotCommand;

/**
 * Utility class to build JSON command strings for the Alpha Mini robot.
 *
 * All commands are serialized to JSON and sent over Bluetooth.
 */
public class CommandBuilder {

    private static final Gson gson = new Gson();

    // ── Simple action commands ────────────────────────────────────────────────

    public static String wave()       { return action(RobotCommand.CMD_WAVE); }
    public static String dance()      { return action(RobotCommand.CMD_DANCE); }
    public static String forward()    { return action(RobotCommand.CMD_FORWARD); }
    public static String backward()   { return action(RobotCommand.CMD_BACKWARD); }
    public static String turnLeft()   { return action(RobotCommand.CMD_TURN_LEFT); }
    public static String turnRight()  { return action(RobotCommand.CMD_TURN_RIGHT); }
    public static String sitDown()    { return action(RobotCommand.CMD_SIT_DOWN); }
    public static String standUp()    { return action(RobotCommand.CMD_STAND_UP); }
    public static String stop()       { return action(RobotCommand.CMD_STOP); }

    /** Build a TTS speak command with the given text. */
    public static String speak(String text) {
        JsonObject params = new JsonObject();
        params.addProperty("text", text);
        return buildJson(RobotCommand.TYPE_TTS, RobotCommand.CMD_SPEAK, params);
    }

    /** Build a WiFi configuration command. */
    public static String wifiConfig(String ssid, String password) {
        JsonObject obj = new JsonObject();
        obj.addProperty("type", RobotCommand.TYPE_WIFI_CONFIG);
        obj.addProperty("ssid", ssid);
        obj.addProperty("password", password);
        return gson.toJson(obj) + "\n";
    }

    /** Build a battery query command. */
    public static String getBattery() {
        return buildJson(RobotCommand.TYPE_QUERY, RobotCommand.CMD_BATTERY, null);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static String action(String command) {
        return buildJson(RobotCommand.TYPE_ACTION, command, null);
    }

    private static String buildJson(String type, String command, JsonObject params) {
        JsonObject obj = new JsonObject();
        obj.addProperty("type", type);
        obj.addProperty("command", command);
        obj.add("params", params != null ? params : new JsonObject());
        // Append newline so robot can detect message boundary
        return gson.toJson(obj) + "\n";
    }
}
