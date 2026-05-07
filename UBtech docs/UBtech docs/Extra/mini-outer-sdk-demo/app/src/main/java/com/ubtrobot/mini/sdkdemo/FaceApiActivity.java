package com.ubtrobot.mini.sdkdemo;

import android.app.Activity;
import android.os.Bundle;
import android.support.annotation.NonNull;
import android.support.annotation.Nullable;
import android.util.Log;
import android.view.View;
import com.ubtechinc.sauron.api.FaceApi;
import com.ubtechinc.sauron.api.FaceFindListener;
import com.ubtechinc.sauron.api.FaceInfo;
import com.ubtechinc.sauron.api.FaceTrackListener;
import com.ubtrobot.commons.ResponseListener;
import java.util.List;

/**
 * FaceApi的测试方法
 */

public class FaceApiActivity extends Activity {
  private static final String TAG = "FaceApiActivity";
  private FaceApi faceApi;

  @Override protected void onCreate(@Nullable Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);
    setContentView(R.layout.face_api_layout);

    initRobot();
  }

  /**
   * 初始化接口类实例
   */
  private void initRobot() {
    faceApi = FaceApi.get();
  }

  /**
   * 检测机器人当前是否处于录入过程
   */
  public void checkFaceInsertState(View view) {
    faceApi.checkFaceInsertState(new ResponseListener<Void>() {
      @Override public void onResponseSuccess(Void aVoid) {
        Log.i(TAG, "checkFaceInsertState接口调用成功！");
      }

      @Override public void onFailure(int errorCode, @NonNull String errorMsg) {
        Log.i(TAG, "checkFaceInsertState执行表情错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 人脸分析，检测当前画面的人脸，并进行分析，获得年龄和性别的等信息，注：不包括是否熟人的信息
   */
  public void faceAnalyze(View view) {
    faceApi.faceAnalyze(15, new ResponseListener<List<FaceInfo>>() {
      @Override public void onResponseSuccess(List<FaceInfo> faceInfos) {
        for (FaceInfo faceInfo : faceInfos) {
          Log.i(TAG, faceInfo.toString());
        }
      }

      @Override public void onFailure(int errorCode, @NonNull String errorMsg) {
        Log.i(TAG, "faceAnalyze接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 即时人脸离线检测,检测当前人脸，检测到人脸立即返回结束
   */
  public void faceDetect(View view) {
    faceApi.faceDetect(15, new ResponseListener<List<FaceInfo>>() {
      @Override public void onResponseSuccess(List<FaceInfo> faceInfos) {
        for (FaceInfo faceInfo : faceInfos) {
          Log.i(TAG, faceInfo.toString());
        }
      }

      @Override public void onFailure(int errorCode, @NonNull String errorMsg) {
        Log.i(TAG, "faceDetect接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 人脸识别，检测当前画面的人脸信息（是否熟人，不包括年龄、性别等信息）
   */
  public void faceRecognize(View view) {
    faceApi.faceRecognize(30, new ResponseListener<List<FaceInfo>>() {
      @Override public void onResponseSuccess(List<FaceInfo> faceInfos) {
        for (FaceInfo faceInfo : faceInfos) {
          Log.i(TAG, faceInfo.toString());
        }
      }

      @Override public void onFailure(int errorCode, @NonNull String errorMsg) {
        Log.i(TAG, "faceRecognize接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 人脸注册skill启动接口
   */
  public void faceRegisterStart(View view) {
    faceApi.startRegister("user_li", "李白", new ResponseListener<String>() {
      @Override public void onResponseSuccess(String msg) {
        Log.i(TAG, "faceRegisterStart调用成功,msg======" + msg);
      }

      @Override public void onFailure(int errorCode, @NonNull String errorMsg) {
        Log.i(TAG, "faceRegisterStart接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 退出人脸录入过程
   */
  public void faceRegisterStop(View view) {
    faceApi.stopRegister("user_li", new ResponseListener<Void>() {
      @Override public void onResponseSuccess(Void aVoid) {
        Log.i(TAG, "faceRegisterStop调用成功!");
      }

      @Override public void onFailure(int errorCode, @NonNull String errorMsg) {
        Log.i(TAG, "faceRegisterStop接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 人脸追踪识别接口
   */
  public void faceTrack(View view) {
    faceApi.faceTrack(15, true, new FaceTrackListener() {
      @Override public void onStart() {
        Log.i(TAG, "faceTrack开始追踪人脸!");
      }

      @Override public void onFaceChange(List<FaceInfo> faceInfos) {
        for (FaceInfo faceInfo : faceInfos) {
          Log.i(TAG, faceInfo.toString());
        }
      }

      @Override public void onStop() {
        Log.i(TAG, "faceTrack停止追踪人脸!");
      }

      @Override public void onFail(int errorCode, String errorMsg) {
        Log.i(TAG, "faceTrack接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 退出人脸追踪识别
   */
  public void stopFaceTrack(View view) {
    faceApi.stopFaceTrack(new ResponseListener<Void>() {
      @Override public void onResponseSuccess(Void aVoid) {
        Log.i(TAG, "stopFaceTrack调用成功!");
      }

      @Override public void onFailure(int errorCode, @NonNull String errorMsg) {
        Log.i(TAG, "stopFaceTrack接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 找人脸，开启后不断转动头部舵机寻找人脸，过程中回调找到人脸列表
   */
  public void findFace(View view) {
    faceApi.findFace(20, new FaceFindListener() {
      @Override public void onPause() {
        Log.i(TAG, "findFace暂停找人脸!");
      }

      @Override public void onStart() {
        Log.i(TAG, "findFace开始找人脸!");
      }

      @Override public void onFaceChange(List<FaceInfo> faceInfos) {
        Log.i(TAG, "findFace找到人脸!");
        for (FaceInfo faceInfo : faceInfos) {
          Log.i(TAG, faceInfo.toString());
        }
      }

      @Override public void onStop() {
        Log.i(TAG, "findFace停止找人脸!");
      }

      @Override public void onFail(int errorCode, String errorMsg) {
        Log.i(TAG, "findFace接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 暂停找人脸，暂停舵机，摄像头不关闭。再次调用findFace() 可继续找脸
   */
  public void pauseFindFace(View view) {
    faceApi.pauseFindFace(new ResponseListener<Void>() {
      @Override public void onResponseSuccess(Void aVoid) {
        Log.i(TAG, "pauseFindFace调用成功!");
      }

      @Override public void onFailure(int errorCode, @NonNull String errorMsg) {
        Log.i(TAG, "pauseFindFace接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  /**
   * 退出找人脸,关闭摄像头，停止舵机
   */
  public void stopFindFace(View view) {
    faceApi.stopFindFace(new ResponseListener<Void>() {
      @Override public void onResponseSuccess(Void aVoid) {
        Log.i(TAG, "stopFindFace调用成功!");
      }

      @Override public void onFailure(int errorCode, @NonNull String errorMsg) {
        Log.i(TAG, "stopFindFace接口返回错误,errorCode:" + errorCode + ",errorMsg:" + errorMsg);
      }
    });
  }

  @Override protected void onDestroy() {
    super.onDestroy();
  }
}
