package com.yourname.alphaminicontroller.model;

import com.google.gson.JsonObject;

/**
 * Represents a JSON command to be sent to the Alpha Mini robot.
 *
 * Format:
 * {
 *   "type": "action",
 *   "command": "wave",
 *   "params": {}
 * }
 */
public class RobotCommand {

    // Command types
    public static final String TYPE_ACTION     = "action";
    public static final String TYPE_TTS        = "tts";
    public static final String TYPE_WIFI_CONFIG = "wifi_config";
    public static final String TYPE_QUERY      = "query";

    // Action commands
    public static final String CMD_WAVE       = "wave";
    public static final String CMD_DANCE      = "dance";
    public static final String CMD_FORWARD    = "walk_forward";
    public static final String CMD_BACKWARD   = "walk_backward";
    public static final String CMD_TURN_LEFT  = "turn_left";
    public static final String CMD_TURN_RIGHT = "turn_right";
    public static final String CMD_SIT_DOWN   = "sit_down";
    public static final String CMD_STAND_UP   = "stand_up";
    public static final String CMD_STOP       = "stop";
    public static final String CMD_SPEAK      = "speak";
    public static final String CMD_BATTERY    = "get_battery";

    private final String type;
    private final String command;
    private final JsonObject params;

    public RobotCommand(String type, String command, JsonObject params) {
        this.type    = type;
        this.command = command;
        this.params  = params != null ? params : new JsonObject();
    }

    public String getType()    { return type; }
    public String getCommand() { return command; }
    public JsonObject getParams() { return params; }
}
