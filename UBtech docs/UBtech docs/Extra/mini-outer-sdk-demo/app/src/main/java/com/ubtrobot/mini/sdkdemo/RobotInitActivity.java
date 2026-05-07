package com.ubtrobot.mini.sdkdemo;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.view.View;

import com.ubtrobot.mini.voice.VoiceListener;
import com.ubtrobot.robotinit.PowerKeyManager;
import com.ubtrobot.robotinit.RobotInitApi;
import com.ubtrobot.robotinit.VolumeManager;


public class RobotInitActivity extends Activity {
    private static final String TAG = "RobotInitActivity";
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_robot_init);


    }

    public void OnRobotInit(View view){
        RobotInitApi.get().init(new RobotInitApi.InitCompleteListener(){

            @Override
            public void onComplete() {
                RobotInitApi.get().initCompleteBehavior("", new VoiceListener() {
                    @Override
                    public void onCompleted() {
                        Log.i(TAG,"onCompleted====");
                    }

                    @Override
                    public void onError(int i, String s) {
                        Log.e(TAG,"i====" + i + ";;s===" + s);
                    }
                });
            }
        });
    }

    public void onSubscirsPower(View view){
        PowerKeyManager.get().subscribePowkeyEvent();
    }

    public void onSubscirsVolume(View view){
        VolumeManager.get().subscribeVolumeEvent();
    }
}
