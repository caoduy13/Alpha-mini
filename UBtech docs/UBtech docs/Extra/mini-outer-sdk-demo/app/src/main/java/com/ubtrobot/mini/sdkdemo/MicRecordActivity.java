package com.ubtrobot.mini.sdkdemo;

import android.app.Activity;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.util.Log;
import android.view.View;

import com.ubt.micrecord.AudioDataCallback;
import com.ubt.micrecord.DoaAngleCallback;
import com.ubt.micrecord.ErrorCallback;
import com.ubt.micrecord.InitCallback;
import com.ubt.micrecord.MicRecordApi;
import com.ubt.speechstate.SpeechBehaviorApi;
import com.ubt.speechstate.TurnHeadApi;
import com.ubtech.utilcode.utils.thread.HandlerUtils;

import java.util.Random;

public class MicRecordActivity extends Activity{
    public static final String TAG = "MicRecordActivity";

    @Override protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.micrecord_api_layout);
        init();
    }

    private void init() {
        MicRecordApi.get().init(new InitCallback() {
            @Override
            public void onSucc() {
                Log.d(TAG,"onSucc");
            }

            @Override
            public void onError() {
                Log.d(TAG,"onError");
            }
        });

        MicRecordApi.get().setErrorCallback(new ErrorCallback() {
            @Override
            public void onError(int errCode) {
                Log.d(TAG,"---onError----errCode = "+errCode);
            }
        });

    }

    public void startRecord(View view) {
        MicRecordApi.get().startRecord(new AudioDataCallback() {
            @Override
            public void onAudio(byte[] data1, byte[] data2) {
//                Log.d(TAG,"onAudio---data1.length = "+data1.length + ", data2.length = "+data2.length);
                //Todo: data1 use for Wakeup, data2 use for asr/nlp

            }
        });
    }

    public void stopRecord(View view) {
        MicRecordApi.get().stopRecord();
    }

    private short lastWakeupAngle = 0;
    public void triggleWakeup(View view) {
        SpeechBehaviorApi.notifyWakeup();
        MicRecordApi.get().setDoaAngleCallback(new DoaAngleCallback() {

            @Override
            public void onDoaAngle(short angle) {
                lastWakeupAngle = angle;
                Log.d(TAG,"onDoaAngle----angle = "+angle);
            }
        });

        MicRecordApi.get().startDOABeamForming();

        HandlerUtils.getMainHandler().postDelayed(new Runnable() {
            @Override
            public void run() {
                SpeechBehaviorApi.notifyReceiveSpeakStart();
            }
        }, 500);

        HandlerUtils.getMainHandler().postDelayed(new Runnable() {
            @Override
            public void run() {
                SpeechBehaviorApi.notifyReceiveSpeakEnd();
                TurnHeadApi.shakeHead(lastWakeupAngle,new TurnHeadApi.MoveHeadCallback() {

                    @Override
                    public void onSucc(int moveAngel,int currMotorAngel) {
                        Log.d(TAG,"---onSucc---moveAngel---currMotorAngel = "+currMotorAngel);
                    }

                    @Override
                    public void onError(int moveAngel,int currMotorAngel) {

                    }
                });
            }
        }, 5000);

        HandlerUtils.getMainHandler().postDelayed(new Runnable() {
            @Override
            public void run() {
                SpeechBehaviorApi.notifyReceiveNlpResult();
            }
        }, 7000);
    }

    public void startTTS(View view) {
        SpeechBehaviorApi.notifyTTSStart();
    }

    public void endTTS(View view) {
        SpeechBehaviorApi.notifyTTSEnd();
    }

    public void triggleTurnHead(View view) {
        int angel = 0;
        Random random = new Random();
        angel = random.nextInt(360);
        Log.d(TAG,"triggleTurnHead---angel = "+angel);
        TurnHeadApi.shakeHead(angel,new TurnHeadApi.MoveHeadCallback() {

            @Override
            public void onSucc(int moveAngel,int currMotorAngel) {
                Log.d(TAG,"---onSucc---moveAngel---currMotorAngel = "+currMotorAngel);
            }

            @Override
            public void onError(int moveAngel,int currMotorAngel) {

            }
        });
    }

}
