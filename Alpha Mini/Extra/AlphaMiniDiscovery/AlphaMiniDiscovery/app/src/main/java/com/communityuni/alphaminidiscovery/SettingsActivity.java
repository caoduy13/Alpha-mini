package com.communityuni.alphaminidiscovery;

import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.communityuni.alphaminidiscovery.databinding.ActivitySettingsBinding;
import com.communityuni.alphaminidiscovery.utils.NetworkScanner;
import com.communityuni.alphaminidiscovery.utils.PrefsManager;

/**
 * SettingsActivity: cấu hình IP robot + auto discover + switches.
 */
public class SettingsActivity extends AppCompatActivity {

    private ActivitySettingsBinding vb;
    private PrefsManager prefs;
    private NetworkScanner scanner;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        vb = ActivitySettingsBinding.inflate(getLayoutInflater());
        setContentView(vb.getRoot());

        prefs = new PrefsManager(this);
        scanner = new NetworkScanner(this);

        vb.toolbar.setNavigationOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                finish();
            }
        });

        vb.edtIp.setText(prefs.getRobotIp());
        vb.switchAutoReconnect.setChecked(prefs.isAutoReconnect());
        vb.switchEmotionAnim.setChecked(prefs.isShowEmotionAnim());

        vb.switchAutoReconnect.setOnCheckedChangeListener((buttonView, isChecked) -> prefs.setAutoReconnect(isChecked));
        vb.switchEmotionAnim.setOnCheckedChangeListener((buttonView, isChecked) -> prefs.setShowEmotionAnim(isChecked));

        vb.btnSaveConnect.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String ip = safeText(vb.edtIp.getText() == null ? null : vb.edtIp.getText().toString());
                if (TextUtils.isEmpty(ip)) {
                    Toast.makeText(SettingsActivity.this, R.string.toast_need_ip, Toast.LENGTH_SHORT).show();
                    return;
                }
                prefs.setRobotIp(ip);
                Toast.makeText(SettingsActivity.this, R.string.toast_connected, Toast.LENGTH_SHORT).show();
                finish();
            }
        });

        vb.btnDiscover.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                vb.progressDiscover.setVisibility(View.VISIBLE);
                Toast.makeText(SettingsActivity.this, R.string.toast_discovering, Toast.LENGTH_SHORT).show();

                scanner.discoverRobotIp(new NetworkScanner.DiscoveryListener() {
                    @Override
                    public void onFound(final String ip) {
                        runOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                vb.progressDiscover.setVisibility(View.GONE);
                                vb.edtIp.setText(ip);
                                prefs.setRobotIp(ip);
                                Toast.makeText(SettingsActivity.this, getString(R.string.toast_discover_done, ip), Toast.LENGTH_LONG).show();
                            }
                        });
                    }

                    @Override
                    public void onNotFound() {
                        runOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                vb.progressDiscover.setVisibility(View.GONE);
                                Toast.makeText(SettingsActivity.this, R.string.toast_discover_none, Toast.LENGTH_LONG).show();
                            }
                        });
                    }
                });
            }
        });

        // About block
        vb.txtAbout.setText(
                getString(R.string.app_version_label) + ": " + BuildConfig.VERSION_NAME + "\n" +
                        getString(R.string.robot_model_label) + ": " + getString(R.string.robot_model_value)
        );
    }

    private static String safeText(String s) {
        return s == null ? "" : s.trim();
    }
}

