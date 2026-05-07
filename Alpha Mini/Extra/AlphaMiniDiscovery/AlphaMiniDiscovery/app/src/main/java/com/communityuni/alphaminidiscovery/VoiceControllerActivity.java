package com.communityuni.alphaminidiscovery;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.view.View;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import android.widget.Button;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.ubtrobot.speech.SpeechApi;
import com.ubtrobot.speech.listener.TTsListener;

import java.util.ArrayList;
import java.util.Locale;

public class VoiceControllerActivity extends AppCompatActivity {

    private static final int REQ_RECORD_AUDIO = 1001;

    private TextView txtStatus;
    private TextView txtResult;
    private Button btnStart;
    private Button btnSend;
    private SpeechRecognizer speechRecognizer;
    private boolean isListening = false;
    private XiaozhiWsClient xiaozhi;
    private String lastUserText = "";

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_voice_controller);

        txtStatus = findViewById(R.id.txtStatus);
        txtResult = findViewById(R.id.txtResult);
        btnStart = findViewById(R.id.btnStart);
        btnSend = findViewById(R.id.btnSend);

        // WS URL Xiaozhi (cloud)
        final String wsUrl = "wss://api.tenclass.net/xiaozhi/v1/";
        xiaozhi = new XiaozhiWsClient(wsUrl, new XiaozhiWsClient.Listener() {
            @Override
            public void onStatus(final String status) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        txtStatus.setText(status);
                    }
                });
            }

            @Override
            public void onReplyText(final String text) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        txtResult.setText(text);
                        txtStatus.setText("Xiaozhi trả lời");
                    }
                });
                // Ưu tiên: TTS on robot
                speakOnRobot(text);
            }
        });
        xiaozhi.connect();

        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
        speechRecognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle params) { txtStatus.setText("Nói đi..."); }
            @Override public void onBeginningOfSpeech() { }
            @Override public void onRmsChanged(float rmsdB) { }
            @Override public void onBufferReceived(byte[] buffer) { }
            @Override public void onEndOfSpeech() { txtStatus.setText("Đang nhận diện..."); }
            @Override public void onError(int error) {
                // Lỗi nhẹ, chỉ thông báo chứ không chặn lần sau
                txtStatus.setText("Lỗi nhận diện: " + error + ". Thử lại.");
                isListening = false;
            }

            @Override
            public void onResults(Bundle results) {
                isListening = false;
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (matches != null && !matches.isEmpty()) {
                    String text = matches.get(0);
                    txtResult.setText(text);
                    txtStatus.setText("Đã nhận: " + text);
                    lastUserText = text;
                    handleCommand(text.toLowerCase(Locale.getDefault()));
                } else {
                    txtStatus.setText("Không nghe rõ. Thử lại.");
                }
            }

            @Override public void onPartialResults(Bundle partialResults) { }
            @Override public void onEvent(int eventType, Bundle params) { }
        });

        btnStart.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startVoiceRecognition();
            }
        });

        btnSend.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                stopVoiceRecognition();
            }
        });

        // Yêu cầu quyền micro nếu chưa có
        ensureRecordAudioPermission();
    }

    private void ensureRecordAudioPermission() {
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(
                    this,
                    new String[]{android.Manifest.permission.RECORD_AUDIO},
                    REQ_RECORD_AUDIO
            );
        }
    }

    private void startVoiceRecognition() {
        if (isListening) {
            return;
        }
        isListening = true;
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "vi-VN");
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        speechRecognizer.startListening(intent);
        txtStatus.setText("Đang lắng nghe...");
    }

    private void stopVoiceRecognition() {
        if (!isListening) {
            return;
        }
        speechRecognizer.stopListening();
        txtStatus.setText("Đang xử lý...");
    }

    private void handleCommand(String command) {
        // Hybrid (Tier 1 + Tier 2):
        // - Gửi text lên Xiaozhi qua WebSocket
        // - Nhận reply -> robot TTS
        if (lastUserText == null || lastUserText.trim().isEmpty()) {
            return;
        }
        txtStatus.setText("Đang gửi Xiaozhi...");
        xiaozhi.sendUserText(lastUserText);
    }

    private void speakOnRobot(String text) {
        try {
            // playTTs: TTS trên robot (nếu SDK/robot hỗ trợ remote)
            SpeechApi.get().playTTs(text, new TTsListener() {
                @Override
                public void onTtsBegin() { }

                @Override
                public void onTtsVolumeChange(int volume) { }

                @Override
                public void onTtsCompleted() { }

                @Override
                public void onError(int code, String msg) {
                    final String s = "TTS robot lỗi: " + code + " " + msg;
                    runOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            txtStatus.setText(s);
                        }
                    });
                }
            });
        } catch (Throwable t) {
            final String s = "Không gọi được TTS robot: " + t.getMessage();
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    txtStatus.setText(s);
                }
            });
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (speechRecognizer != null) {
            speechRecognizer.destroy();
            speechRecognizer = null;
        }
        if (xiaozhi != null) {
            xiaozhi.disconnect();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_RECORD_AUDIO) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                txtStatus.setText("Đã cấp quyền micro. Nhấn NÓI để điều khiển.");
            } else {
                txtStatus.setText("Ứng dụng cần quyền micro để nhận giọng nói.");
            }
        }
    }
}

