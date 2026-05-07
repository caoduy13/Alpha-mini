package com.communityuni.alphaminidiscovery;

import android.app.Application;

import com.ubtrobot.mini.SDKInit;
import com.ubtrobot.mini.properties.sdk.Path;
import com.ubtrobot.mini.properties.sdk.PropertiesApi;

public class AlphaApp extends Application {

    @Override
    public void onCreate() {
        super.onCreate();
        PropertiesApi.setRootPath(Path.DIR_MINI_FILES_SDCARD_ROOT);
        SDKInit.initialize(this);
    }

//    @Override
//    protected void onStartFailed(UbtSkillInfo ubtSkillInfo) {
//
//    }
//
//    @Override
//    protected void onInterrupted() {
//
//    }

}
