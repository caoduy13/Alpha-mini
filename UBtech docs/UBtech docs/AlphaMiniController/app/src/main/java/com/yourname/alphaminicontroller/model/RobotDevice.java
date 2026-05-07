package com.yourname.alphaminicontroller.model;

/**
 * Represents a discovered Bluetooth device.
 * Wraps BluetoothDevice with extra metadata.
 */
public class RobotDevice {

    private final String name;
    private final String macAddress;
    private final boolean isAlphaMini;

    public RobotDevice(String name, String macAddress) {
        this.name = (name != null && !name.isEmpty()) ? name : "Unknown Device";
        this.macAddress = macAddress;
        // Flag devices whose name contains "AlphaMini" (case-insensitive)
        this.isAlphaMini = this.name.toLowerCase().contains("alphamini")
                || this.name.toLowerCase().contains("alpha mini")
                || this.name.toLowerCase().contains("ubtech");
    }

    public String getName() { return name; }

    public String getMacAddress() { return macAddress; }

    public boolean isAlphaMini() { return isAlphaMini; }

    @Override
    public String toString() {
        return "RobotDevice{name='" + name + "', mac='" + macAddress + "'}";
    }
}
