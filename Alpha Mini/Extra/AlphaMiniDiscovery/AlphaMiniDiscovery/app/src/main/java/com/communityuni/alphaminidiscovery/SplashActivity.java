package com.communityuni.alphaminidiscovery;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

/**
 * Splash screen: fade-in và tự chuyển sang MainActivity sau 2 giây.
 */
public class SplashActivity extends AppCompatActivity {

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable goNext = new Runnable() {
        @Override
        public void run() {
            Intent i = new Intent(SplashActivity.this, MainActivity.class);
            startActivity(i);
            finish();
        }
    };

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_splash);

        View logo = findViewById(R.id.imgLogo);
        View title = findViewById(R.id.txtTitle);
        View subtitle = findViewById(R.id.txtSubtitle);

        // Fade-in đơn giản
        logo.setAlpha(0f);
        title.setAlpha(0f);
        subtitle.setAlpha(0f);
        logo.animate().alpha(1f).setDuration(500).start();
        title.animate().alpha(1f).setStartDelay(120).setDuration(600).start();
        subtitle.animate().alpha(1f).setStartDelay(220).setDuration(600).start();

        handler.postDelayed(goNext, 2000);
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(goNext);
        super.onDestroy();
    }
}

