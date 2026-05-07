package com.ubtrobot.sample.mobile.channel.activity;


import android.app.Activity;
import android.content.Context;
import android.os.Bundle;
import android.support.annotation.NonNull;
import android.util.Log;
import android.view.View;
import android.widget.EditText;
import android.widget.Toast;

import com.common.channel.net.INet;
import com.common.channel.net.callback.ConnectionCallback;
import com.common.channel.net.exception.NetException;
import com.common.channel.net.listener.ConnectionStateListener;
import com.ubtrobot.lan.SocketConnectParam;
import com.ubtrobot.lib.communation.mobile.Channel;
import com.ubtrobot.lib.communation.mobile.CommChannelManager;
import com.ubtrobot.lib.communation.mobile.RobotMaster;
import com.ubtrobot.lib.communation.mobile.connection.Connection;
import com.ubtrobot.lib.communation.mobile.connection.RobotServiceProxy;
import com.ubtrobot.lib.communation.mobile.connection.RobotSkillsProxy;
import com.ubtrobot.lib.communation.mobile.connection.callback.PushMessageListener;
import com.ubtrobot.lib.communation.mobile.connection.callback.ResultCallback;
import com.ubtrobot.lib.communation.mobile.connection.event.EventSubscriber;
import com.ubtrobot.lib.communation.mobile.connection.message.CallException;
import com.ubtrobot.lib.communation.mobile.connection.message.Event;
import com.ubtrobot.lib.communation.mobile.connection.message.PushMessage;
import com.ubtrobot.lib.communation.mobile.connection.message.Request;
import com.ubtrobot.lib.communation.mobile.connection.message.Response;
import com.ubtrobot.lib.communation.mobile.connection.message.ResponseCallback;
import com.ubtrobot.lib.communation.mobile.connection.transport.ProtoParam;
import com.ubtrobot.lib.robot.proto.ProtoClass;
import com.ubtrobot.sample.mobile.channel.R;
import com.ubtrobot.security.security.EncryptAlgorithm;

import java.net.InetSocketAddress;

/**
 * Created by Mark.Zhang on 2017/8/30.
 */

public class LanTestActivity extends Activity {

    private static final String TAG = "lan-test-net";

    private static final int LAN_PACKET_PUB_TCP_PORT = 9000;

    private CommChannelManager mCommChannelManager;
    private Channel mChannel;
    private RobotMaster mMaster;
    private RobotSkillsProxy mRobotSkillsProxy;

    private Context mContext;

    private Connection mLanConnection;
    private ConnectionStateListener mConnectionStateListener = new ConnectionStateListener() {
        @Override
        public void onStateChanged(INet.ConnectionState newState) {
            Log.d("lan-test-net", " new state:" + newState);
            //Toast.makeText(mContext, "state changed:" + newState, Toast.LENGTH_SHORT).show();
        }
    };

    private EditText mEtTtsText, mEtActionName, mEtIpAddress;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_lan_net);

        mContext = this;
        //((TextView)findViewById(R.id.tv_name)).setText("from:" + from + " to:" + to);

        mEtTtsText = (EditText) findViewById(R.id.et_tts_text);
        mEtActionName = (EditText) findViewById(R.id.et_action_text);
        mEtIpAddress = (EditText) findViewById(R.id.et_to);

        CommChannelManager.init(getApplicationContext());
        mCommChannelManager = CommChannelManager.getInstance();
        mChannel = CommChannelManager.getInstance().createChannel("test");
        mLanConnection = mChannel.createSocketConnection();

        mLanConnection.registerConnectionStateListener(mConnectionStateListener);

        //mRobotSkillsProxy = mLanConnection.createRobotSkillsProxy();
        mMaster = mCommChannelManager.createRobotMaster(mLanConnection);
        mRobotSkillsProxy = mMaster.createRobotSkillsProxy();

        mLanConnection.addPushMessageListener(mPushMessageListener);

        Log.d(TAG, "ConnectionState:" + mLanConnection.getState());

        try {
            mLanConnection.setEncryptAlgorithm4TransferData(EncryptAlgorithm.NONE);
        } catch (Exception ex) {
            Log.e(TAG, "Set encrypt algorithm fail!", ex);
        }


    }

    public void onDestroy() {
        mLanConnection.removePushMessageListener(mPushMessageListener);
        mLanConnection.unregisterConnectionStateListener(mConnectionStateListener);

        super.onDestroy();
    }

    private PushMessageListener mPushMessageListener = new PushMessageListener() {
        @Override
        public void onReceive(PushMessage message) {
            Log.d(TAG, "Recive a push message:" + message);
        }
    };

    public void onClick(View view) {
        switch (view.getId()) {
            case R.id.btn_connect:
                mLanConnection.connect(new SocketConnectParam(new InetSocketAddress(mEtIpAddress.getText().toString(),
                                LAN_PACKET_PUB_TCP_PORT)),
                        new ConnectionCallback() {
                            @Override
                            public void onSuccess() {
                                Log.i(TAG, "connect success");
                                Toast.makeText(mContext, "connect success", Toast.LENGTH_SHORT).show();

                            }

                            @Override
                            public void onFail(@NonNull NetException ex) {
                                Log.i(TAG, "connect fail", ex);
                                Toast.makeText(mContext, "connect fail", Toast.LENGTH_SHORT).show();
                            }

                        });


                break;

            case R.id.btn_disconnect:
                mLanConnection.disconnect(new ConnectionCallback() {
                    @Override
                    public void onSuccess() {
                        Log.d(TAG, "disconnect success");
                        Toast.makeText(mContext, "disconnect success", Toast.LENGTH_SHORT).show();
                    }

                    @Override
                    public void onFail(@NonNull NetException exception) {
                        Log.e(TAG, "disconnect fail");
                        Toast.makeText(mContext, "disconnect success", Toast.LENGTH_SHORT).show();
                    }
                });
                break;

            case R.id.btn_sub:
                try {
                    mLanConnection.setEncryptAlgorithm4TransferData(EncryptAlgorithm.AES_IJM_YJYM_128);
                } catch (Exception ex) {
                    Log.e(TAG, "Set encrypt algorithm fail!", ex);
                }

                mLanConnection.subscribe(mEventSubscriber, "ubtrobot.event.test", new ResultCallback() {
                    @Override
                    public void onSuccess() {
                        Log.i(TAG, "subscribe success!");
                    }

                    @Override
                    public void onFail(int code, String message) {
                        Log.e(TAG, "subscribe fail! errCode:" + code + " dsc:" + message);
                    }
                });
                break;

            case R.id.btn_unsub:
                mLanConnection.unsubscribe(mEventSubscriber, new ResultCallback() {
                    @Override
                    public void onSuccess() {
                        Log.i(TAG, "unsubscribe success!");
                    }

                    @Override
                    public void onFail(int code, String message) {
                        Log.e(TAG, "unsubscribe fail! errCode:" + code + " dsc:" + message);
                    }
                });
                break;

            case R.id.btn_call_app:

                ProtoParam param = ProtoParam.pack(ProtoClass.ProtoText.newBuilder().setText("off").build());

                mRobotSkillsProxy.call("/robot_test/ubtrobot/test", param,new ResponseCallback() {
                    @Override
                    public void onResponse(Request req, Response res) {
                        Log.i(TAG, "Receive a response. res:" + res);
                    }

                    @Override
                    public void onFailure(Request req, CallException e) {
                        Log.e(TAG, "call a doRequest fail.", e);
                    }
                });

                break;

            case R.id.btn_call_service:

                param = ProtoParam.pack(ProtoClass.ProtoText.newBuilder().setText("off").build());

                RobotServiceProxy service = mMaster.createRobotSystemServiceProxy("communication");
                service.call("/ubtrobot/communication/test", param,new ResponseCallback() {
                    @Override
                    public void onResponse(Request req, Response res) {
                        Log.i(TAG, "Receive a service response. res:" + res);
                    }

                    @Override
                    public void onFailure(Request req, CallException e) {
                        Log.e(TAG, "call a service doRequest fail.", e);
                    }
                });

                break;


            case R.id.btn_play_tts:

                new Thread() {
                    public void run() {

                        //同步调用应用
                        ProtoParam param = ProtoParam.pack(ProtoClass.ProtoText.newBuilder()
                                .setText(mEtTtsText.getText().toString()).build());
                        try {
                            Response response = mRobotSkillsProxy.call("/ubtrobot/test/speech", param);
                            Log.i(TAG, "Receive res:" + response);
                        } catch (CallException ex) {
                            Log.e(TAG, "call fail!", ex);
                        }


                    }
                }.start();
                break;

            case R.id.btn_dance:

                param = ProtoParam.pack(ProtoClass.ProtoText.newBuilder()
                        .setText(mEtActionName.getText().toString()).build());

                mRobotSkillsProxy.call("/ubtrobot/sample/motion/test", param, new ResponseCallback() {
                    @Override
                    public void onResponse(Request req, Response res) {

                    }

                    @Override
                    public void onFailure(Request req, CallException e) {

                    }
                });
                break;

            default:
                Log.i(TAG, "Onclick view:" + view.getId());

        }
    }


    private EventSubscriber mEventSubscriber = new EventSubscriber() {
        @Override
        public void onEventPublish(Event event) {
            Log.i(TAG, "Receive event:" + event);
        }
    };


}
