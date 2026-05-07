package com.communityuni.alphaminidiscovery;

import androidx.appcompat.app.AppCompatActivity;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.Toast;

import com.ubtrobot.masterevent.protos.RobotGestures;
import com.ubtrobot.transport.message.CallException;
import com.ubtrobot.transport.message.Request;
import com.ubtrobot.transport.message.Response;
import com.ubtrobot.transport.message.ResponseCallback;

import ubtechinc.com.standupsdk.FallClimbEventReceiver;
import ubtechinc.com.standupsdk.GetRobotGestureCallback;
import ubtechinc.com.standupsdk.StandUpApi;

public class StandUpApiActivity extends AppCompatActivity {
    private static final String TAG = "StandupApiActivity";
    private FallClimbEventReceiver fallClimbEventReceiver;
    MessageBox messageBox=null;
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_standup_api);
        fallClimbEventReceiver = new FallClimbEventReceiver() {

            @Override public void onFallclimb(RobotGestures.FallClimbType fallClimbType) {
                Log.i(TAG,"fallClimbType===" + fallClimbType);
            }

        };
        StandUpApi.get().subscribeFallClimbEvent(fallClimbEventReceiver);
    }

    public void getRobotGesture(View view) {
        RobotGestures.GestureType gestureType=StandUpApi.get().getRobotGesture();

        Log.i(TAG,"gestureType========" + gestureType);
        Toast.makeText(this,"gestureType========" + gestureType,Toast.LENGTH_LONG).show();
    }

    public void getRobotGestureSync(View view) {
      StandUpApi.get().getRobotGestureSync(new GetRobotGestureCallback() {
            @Override
            protected void getRobotGesture(RobotGestures.GestureType gestureType) {
                Toast.makeText(StandUpApiActivity.this,"gestureTypeSync========" + gestureType,Toast.LENGTH_LONG).show();
            }

            @Override
            public void onFailure(Request request, CallException e) {
                Toast.makeText(StandUpApiActivity.this,"gestureTypeSyncErr========" + e.getLocalizedMessage(),Toast.LENGTH_LONG).show();

            }
        });
    }
    public void standup(View view) {
        StandUpApi.get().standUp(new ResponseCallback() {
            @Override
            public void onResponse(Request request, Response response) {
                messageBox=new MessageBox(StandUpApiActivity.this);
                messageBox.setRequest(request);
                messageBox.setResponse(response);
                messageBox.setException(null);
                messageBox.showDialog();
            }
            @Override
            public void onFailure(Request request, CallException e) {
                messageBox=new MessageBox(StandUpApiActivity.this);
                messageBox.setRequest(request);
                messageBox.setResponse(null);
                messageBox.setException(e);
                messageBox.showDialog();
            }
        });
    }
    public void sitdown(View view) {
        StandUpApi.get().sitdown(new ResponseCallback() {
            @Override
            public void onResponse(Request request, Response response) {
                messageBox=new MessageBox(StandUpApiActivity.this);
                messageBox.setRequest(request);
                messageBox.setResponse(response);
                messageBox.setException(null);
                messageBox.show();
            }

            @Override
            public void onFailure(Request request, CallException e) {
                messageBox=new MessageBox(StandUpApiActivity.this);
                messageBox.setRequest(request);
                messageBox.setResponse(null);
                messageBox.setException(e);
                messageBox.showDialog();
            }
        });
    }
    public void squatdown(View view) {
        StandUpApi.get().squatdown(new ResponseCallback() {
            @Override
            public void onResponse(Request request, Response response) {
                messageBox=new MessageBox(StandUpApiActivity.this);
                messageBox.setRequest(request);
                messageBox.setResponse(response);
                messageBox.setException(null);
                messageBox.showDialog();
            }

            @Override
            public void onFailure(Request request, CallException e) {
                messageBox=new MessageBox(StandUpApiActivity.this);
                messageBox.setRequest(request);
                messageBox.setResponse(null);
                messageBox.setException(e);
                messageBox.showDialog();
            }
        });
    }
    public void getRobotFallStatus(View view) {
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        StandUpApi.get().unsubscribeFallClimbEvent(fallClimbEventReceiver);
    }
}
