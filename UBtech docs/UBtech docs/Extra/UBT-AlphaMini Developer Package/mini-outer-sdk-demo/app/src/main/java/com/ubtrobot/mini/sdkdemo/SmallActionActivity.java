package com.ubtrobot.mini.sdkdemo;

import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;
import android.view.View;

import com.ubtrobot.small.action.SmallAction;
import com.ubtrobot.small.action.SmallActionApi;

import java.util.List;

/**
 * tips: logcat: tag: SmallAction
 */
public class SmallActionActivity extends AppCompatActivity {

    private List<SmallAction> smallActions;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_small_action);
    }

    public void testListSmallActions(View view) {
        smallActions = SmallActionApi.get().listSmallActions();
    }

    public void testPlay(View view) {
        if(smallActions!=null && smallActions.size()>0) {
            SmallActionApi.get().play(smallActions.get(0));
        }
    }

    public void testStop(View view) {
        if(smallActions!=null && smallActions.size()>0) {
            SmallActionApi.get().stop(smallActions.get(0));
        }
    }

}
