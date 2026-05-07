package com.ubtrobot.mini.speech.framework.demo;

import android.content.Intent;
import android.os.SystemClock;
import android.util.Log;
import com.ubtech.utilcode.utils.thread.ThreadPool;
import com.ubtrobot.mini.speech.framework.AbstractSpeechApplication;
import com.ubtrobot.service.ServiceModules;
import com.ubtrobot.speech.SpeechService;
import com.ubtrobot.speech.SpeechSettings;

public class SpeechApplication extends AbstractSpeechApplication {
  @Override public void onCreate() {
    super.onCreate();
    startService(new Intent(this, DemoMasterService.class));
    ServiceModules.declare(SpeechSettings.class,
        (aClass, moduleCreatedNotifier) -> moduleCreatedNotifier.notifyModuleCreated(
            DemoSpeech.INSTANCE.createSpeechSettings()));

    ServiceModules.declare(SpeechService.class,
        (aClass, moduleCreatedNotifier) -> ThreadPool.runOnNonUIThread(() -> {
          while (DemoSpeech.INSTANCE.createSpeechService() == null) {
            SystemClock.sleep(5);
          }
          Log.d("Logic", "Speech Service create ok..");
          moduleCreatedNotifier.notifyModuleCreated(DemoSpeech.INSTANCE.createSpeechService());
        }));
  }
}
