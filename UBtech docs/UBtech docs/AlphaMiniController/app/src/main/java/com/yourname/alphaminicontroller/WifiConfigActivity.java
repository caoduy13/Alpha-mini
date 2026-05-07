package com.yourname.alphaminicontroller;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.EditText;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.snackbar.Snackbar;
import com.yourname.alphaminicontroller.bluetooth.BluetoothService;
import com.yourname.alphaminicontroller.utils.CommandBuilder;

/**
 * Screen for sending WiFi credentials to the Alpha Mini robot via Bluetooth.
 *
 * The robot uses this to connect to the local network for cloud services.
 * Format sent:  {"type":"wifi_config","ssid":"...","password":"..."}
 */
public class WifiConfigActivity extends AppCompatActivity {

    private EditText etSsid;
    private EditText etPassword;
    private TextView tvWifiStatus;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_wifi_config);

        etSsid      = findViewById(R.id.et_ssid);
        etPassword  = findViewById(R.id.et_password);
        tvWifiStatus = findViewById(R.id.tv_wifi_status);

        ((MaterialButton) findViewById(R.id.btn_send_wifi)).setOnClickListener(v -> {
            String ssid     = etSsid.getText().toString().trim();
            String password = etPassword.getText().toString();

            if (ssid.isEmpty()) {
                showSnack("Please enter the WiFi SSID");
                return;
            }

            String json = CommandBuilder.wifiConfig(ssid, password);

            // Dispatch to BluetoothService
            Intent intent = new Intent(this, BluetoothService.class);
            intent.setAction(BluetoothService.ACTION_SEND);
            intent.putExtra(BluetoothService.EXTRA_COMMAND, json);
            startService(intent);

            tvWifiStatus.setText("✔ WiFi config sent to robot!\nSSID: " + ssid);
            tvWifiStatus.setTextColor(getColor(R.color.connected));
            tvWifiStatus.setVisibility(View.VISIBLE);

            showSnack(getString(R.string.wifi_sent));
        });
    }

    private void showSnack(String msg) {
        Snackbar.make(findViewById(android.R.id.content), msg, Snackbar.LENGTH_SHORT).show();
    }
}
