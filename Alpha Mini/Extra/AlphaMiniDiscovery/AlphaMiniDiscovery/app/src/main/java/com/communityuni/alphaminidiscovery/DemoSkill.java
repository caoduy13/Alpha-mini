package com.communityuni.alphaminidiscovery;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

import androidx.annotation.NonNull;

import com.ubtechinc.skill.MiniMasterSkill;
import com.ubtechinc.skill.SkillHelper;
import com.ubtrobot.commons.ResponseListener;
import com.ubtrobot.master.Master;
import com.ubtrobot.master.annotation.Call;
import com.ubtrobot.master.context.ContextRunnable;
import com.ubtrobot.mini.sysevent.event.base.KeyEvent;
import com.ubtrobot.speech.protos.Speech;
import com.ubtrobot.transport.message.Request;
import com.ubtrobot.transport.message.Responder;

public class DemoSkill extends MiniMasterSkill {
    private final static String TAG = "DemoSkill";

    @Override
    protected boolean onHeadTapEvent(KeyEvent keyEvent) {
        Log.d(TAG, "onHeadTapEvent: " + keyEvent);
        // Khi chạm đầu, mở app voicebot và yêu cầu bắt đầu trò chuyện
        try {
            Intent intent = new Intent();
            intent.setClassName("info.dourok.voicebot", "info.dourok.voicebot.MainActivity");
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            intent.putExtra("start_conversation", true);
            getApplicationContext().startActivity(intent);
        } catch (Throwable t) {
            Log.e(TAG, "Failed to start voicebot app", t);
        }
        // true = đã xử lý sự kiện
        return true;
    }

    @Override
    protected void onWakeUpEvent(Speech.WakeupParam wakeupParam) {
    }

    @Override
    protected boolean isNeedWakeUpEvent() {
        return false;
    }

    @Override
    protected boolean isNeedHeadTapEvent() {
        // Đăng ký nhận sự kiện chạm đầu
        return true;
    }

    @Call(path = "/demo/startSkill")
    public void onStartSkill(Request request, final Responder responder){
        Log.d(TAG,"onStartSkill---");
        //TODO:
        responder.respondSuccess();
    }

    public static void startThisSkill() {
        SkillHelper.startSkillByIntent("startSkill", null, new ResponseListener<Void>() {
            @Override
            public void onResponseSuccess(Void aVoid) {
                Log.d(TAG,"onResponseSuccess");
            }

            @Override
            public void onFailure(int i, @NonNull String s) {
                Log.d(TAG,"onFailure");
            }
        });
    }

    public static void stopThisSkill() {
        Master.get().execute(DemoSkill.class, new ContextRunnable<DemoSkill>() {
            @Override
            public void run(DemoSkill skill) {
                skill.stopSkill(new Bundle());
            }
        });
    }
}
