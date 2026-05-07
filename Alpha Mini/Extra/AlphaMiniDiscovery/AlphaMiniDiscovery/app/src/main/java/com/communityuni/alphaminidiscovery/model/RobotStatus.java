package com.communityuni.alphaminidiscovery.model;

/**
 * Model parse từ response của robot.
 *
 * Response ví dụ:
 *   {"status":"ok","session_active":true}
 */
public class RobotStatus {
    public String status;
    public boolean session_active;
}

