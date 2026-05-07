package com.ubtrobot.mini.sdkdemo;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.support.annotation.NonNull;
import android.support.annotation.Nullable;
import android.util.Log;
import android.view.View;
import com.ubtrobot.action.ActionApi;
import com.ubtrobot.action.receiver.ActionStoppedReceiver;
import com.ubtrobot.commons.ResponseListener;
import com.ubtrobot.motion.protos.Motion;
import java.util.List;
/**
 * ActionApi的测试方法
 */

public class ActionApiActivity extends Activity {
    private static final String TAG = "ActionApiActivity";
    private ActionApi actionApi;
    private ActionStoppedReceiver receiver;


    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.action_api_layout);

        initRobot();
    }

    /**
     * 初始化接口类实例
     */
    private void initRobot() {
        actionApi = ActionApi.get();
    }

    /**
     * 获取动作列表
     *
     * @param view
     */
    public void getActionList(View view) {
        List<Motion.Action> actionList = actionApi.getActionList();
        for (Motion.Action actionInfo : actionList) {
            Log.i(TAG, actionInfo.toString());
        }
        Log.i(TAG, "getActionList接口调用成功!");
    }

    /**
     * 获取动作列表 ,自定义表情资源存放在/sdcard/customize/actions目录
     *
     * 系统版本需v0.0.3以上
     *
     * @param view
     */
    public void getCustomizeActionList(View view) {
        List<Motion.Action> actionList = actionApi.getCustomizeActionList();
        for (Motion.Action actionInfo : actionList) {
            Log.i(TAG, actionInfo.toString());
        }
        Log.i(TAG, "getActionList接口调用成功!");
    }

    /**
     * 执行动作,以dance_0002为例
     *
     * @param view
     */
    public void playAction(View view) {
        actionApi.playAction("dance_0002", new ResponseListener<Void>() {
            @Override public void onResponseSuccess(Void aVoid) {

            }

            @Override public void onFailure(int i, @NonNull String s) {

            }
        });
        Log.i(TAG, "playAction 接口调用成功!");
    }

    /**
     * 执行自定义动作
     *
     * @param view
     */
    public void playCustomizeAction(View view) {
        actionApi.playCustomizeAction("dance_0002", new ResponseListener<Void>() {
            @Override public void onResponseSuccess(Void aVoid) {

            }

            @Override public void onFailure(int i, @NonNull String s) {

            }
        });

        Log.i(TAG, "playCustomizeAction 接口调用成功!");
    }

    /**
     * 停止动作
     *
     * @param view
     */
    public void stopAction(View view) {
        actionApi.playAction("dance_0001", null);
        Log.i(TAG, "playAction 接口调用成功！");
        new Handler().postDelayed(new Runnable() {
            @Override public void run() {
                actionApi.stopAction(new ResponseListener<Void>() {
                    @Override
                    public void onResponseSuccess(Void aVoid) {
                        Log.i(TAG, "stopAction 接口调用成功！");
                    }

                    @Override
                    public void onFailure(int errorCode, @NonNull String errorMsg) {
                        Log.i(TAG, "playAction执行表情错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
                    }
                });
            }
        }, 1000);
    }

    /**
     * 机器人是否在执行动作
     *
     * @param view
     */
    public void isPlayingAction(View view) {
        actionApi.playAction("dance_0002", null);
        Log.i(TAG, "playAction 接口调用成功！");

        new Handler().postDelayed(new Runnable() {
            @Override public void run() {
                Log.i(TAG, "isPlayingAction接口调用返回" + actionApi.isPlaying());

            }
        }, 1000);
    }

    /**
     * 是否是高危动作
     *
     * @param view
     */
    public void isDangerousAction(View view) {
        Log.i(TAG, "isDangerousAction接口调用,dance_0001(少林英雄)动作是否是高危动作:" + actionApi.unsafeAction("dance_0001"));
        Log.i(TAG, "isDangerousAction接口调用,013(打功夫)动作是否是高危动作:" + actionApi.unsafeAction("013"));
    }

    /**
     * 获取机器人正在执行的动作信息
     *
     * @param view
     */
    public void getCurrentActionInfo(View view) {
        List<Motion.Action> actionInfo = actionApi.currentAction();
        if (actionInfo != null) {
            Log.i(TAG, "getCurrentActionInfo接口调用成功!");
            Log.i(TAG, actionInfo.toString());
        }
    }

    /**
     * 订阅动作停止事件
     *
     * @param view
     */
    public void subscribeActionStoppedEvent(View view) {
        receiver = new ActionStoppedReceiver() {
          @Override protected void onActionStopped(String s, Cause cause) {
            Log.i(TAG, "subscribeActionStoppedEvent onActionStopped接收到Action停止事件,cause name:" + cause.name());
          }
        };

        actionApi.subscribeEvent(receiver);
        Log.i(TAG, "subscribeActionStoppedEvent接口调用成功!");
    }

    /**
     * 取消订阅动作停止事件
     *
     * @param view
     */
    public void unsubscribeActionStoppedEvent(View view) {
        if (receiver != null) {
            actionApi.unsubscribeEvent(receiver);
            Log.i(TAG, "unsubscribeActionStoppedEvent接口调用成功！");
        } else {
            Log.i(TAG, "receiver为null,不调用接口!");
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
    }
}
