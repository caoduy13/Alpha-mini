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

/**
 *
 * **1.增加标签**
 *
 * 在`AndroidManifest.xml`文件application标签里，加入如下代码，申请访问麦克风阵列
 * ```
 * <meta-data android:name="ubt-master-app" android:value="third_part_speechservice"/>
 * ```
 * **2. 首次安装该apk后，需要重启机器人**
 *
 * 机器人在每次开机时会检查安装的apk里有没有`third_part_speechservice`标记，如果有的话，
 * 则disable系统内置的访问麦克风阵列的应用SpeechService，把麦克风阵列的访问权让给该apk。
 * 系统内置的SpeechService被disable后，用户将无法访问腾讯叮当语音服务。
 *
 * ## 让出麦克风阵列访问权
 * **1.卸载app或去掉meta-data的标签**
 *
 * **2.重启机器人**
 * 重启机器人后，系统内置的SpeechService将重新获取麦克风阵列访问权限， 用户可以继续使用叮当语音服务。
 *
 * 更多信息参考 << 如何开发App接入语音服务 >> 文档说明
 *
 */
public class MicRecordActivity extends Activity{
    private static final String TAG = DemoApp.DEBUG_TAG;

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
        Log.d(TAG,"onSucc");
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
                        Log.d(TAG,"onError: "+moveAngel+" === "+currMotorAngel);
                    }

                    @Override
                    public void onProgress(int i, int i1) {
                        Log.d(TAG,"onProgress: "+i + " ===== "+i1);
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
                Log.d(TAG,"onError: "+moveAngel+" === "+currMotorAngel);
            }

            @Override
            public void onProgress(int i, int i1) {
                Log.d(TAG,"onProgress: "+i + " ===== "+i1);
            }
        });
    }

}

