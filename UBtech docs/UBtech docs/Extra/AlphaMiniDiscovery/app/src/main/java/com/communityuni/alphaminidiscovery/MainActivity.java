package com.communityuni.alphaminidiscovery;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;

public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
    }

    public void testRobotGestureAPI(View view) {
        Intent intent = new Intent();
        intent.setClass(this, StandUpApiActivity.class);
        startActivity(intent);
    }

    public void openSmallActionActivity(View view) {
        Intent intent = new Intent();
        intent.setClass(this, SmallActionActivity.class);
        startActivity(intent);
    }

    public void skillAPI(View view) {
        Intent intent = new Intent();
        intent.setClass(this, SkillAPIActivity.class);
        startActivity(intent);
    }
}
