package com.alphamini.wifiprovisioner

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.zxing.BarcodeFormat
import com.journeyapps.barcodescanner.BarcodeCallback
import com.journeyapps.barcodescanner.DefaultDecoderFactory
import com.journeyapps.barcodescanner.DecoratedBarcodeView
import com.ubtrobot.master.Master
import com.ubtrobot.speech.SpeechApi
import com.ubtrobot.speech.listener.TTsListener
import java.util.Locale

class MainActivity : AppCompatActivity(), TextToSpeech.OnInitListener {
    companion object {
        private const val TAG = "RobotWifiProvisioner"
        private const val ROBOT_TTS_ENGINE = "com.ubtechinc.alphamini.speech"
    }

    private lateinit var scanner: DecoratedBarcodeView
    private lateinit var statusView: TextView
    private lateinit var startButton: Button
    private lateinit var guideButton: Button
    private lateinit var tts: TextToSpeech
    private var scanning = false
    private var ttsReady = false
    private val pendingSpeechQueue = mutableListOf<Pair<String, String>>()
    private var shouldAutoStartScan = false
    private var waitingGuideThenScan = false
    private var focusGranted = false
    private var pendingInitStatus: Int? = null
    private var retriedWithDefaultEngine = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        scanner = findViewById(R.id.barcodeScanner)
        scanner.setStatusText("")
        scanner.barcodeView.decoderFactory = DefaultDecoderFactory(listOf(BarcodeFormat.QR_CODE))
        statusView = findViewById(R.id.tvStatus)
        startButton = findViewById(R.id.btnStartScan)
        guideButton = findViewById(R.id.btnSpeakGuide)
        try {
            Master.initialize(applicationContext)
        } catch (e: Throwable) {
            Log.w(TAG, "Master.initialize failed", e)
        }
        initTts()

        startButton.setOnClickListener {
            beginScanFlow()
        }
        guideButton.setOnClickListener {
            speakBasicGuide()
        }

        if (!isWifiConnected()) {
            updateStatus("Robot chưa kết nối Wi-Fi, tự động vào chế độ quét QR.")
            shouldAutoStartScan = true
            speakBasicGuide()
        } else {
            updateStatus("Robot đã online Wi-Fi.")
            speak("alpha mini đã kết nối được internet")
        }
    }

    override fun onInit(status: Int) {
        if (!::tts.isInitialized) {
            pendingInitStatus = status
            return
        }
        handleTtsInit(status)
    }

    private fun handleTtsInit(status: Int) {
        Log.d(TAG, "TTS onInit status=$status engine=${tts.defaultEngine}")
        if (status == TextToSpeech.SUCCESS) {
            val langResult = tts.setLanguage(Locale("vi", "VN"))
            if (langResult == TextToSpeech.LANG_MISSING_DATA || langResult == TextToSpeech.LANG_NOT_SUPPORTED) {
                // Fallback to default engine locale but still speak Vietnamese text.
                tts.setLanguage(Locale.getDefault())
            }
            tts.setSpeechRate(0.95f)
            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) = Unit

                override fun onError(utteranceId: String?) {
                    releaseVoicePriority()
                }

                override fun onDone(utteranceId: String?) {
                    releaseVoicePriority()
                    if (utteranceId == "guide-intro" && waitingGuideThenScan) {
                        waitingGuideThenScan = false
                        runOnUiThread { beginScanFlow() }
                    }
                }
            })
            ttsReady = true
            pendingSpeechQueue.forEachIndexed { idx, item ->
                val queueMode = if (idx == 0) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD
                speakNow(item.first, item.second, queueMode)
            }
            pendingSpeechQueue.clear()
            if (shouldAutoStartScan) {
                shouldAutoStartScan = false
                waitingGuideThenScan = true
            }
        } else {
            Log.w(TAG, "TTS init failed with status=$status, retrying with default engine")
            if (!retriedWithDefaultEngine) {
                retriedWithDefaultEngine = true
                initTts(forceDefault = true)
            } else {
                updateStatus("Không khởi tạo được engine giọng nói.")
            }
        }
    }

    private fun beginScanFlow() {
        if (!hasRuntimePermissions()) {
            requestRuntimePermissions()
            return
        }
        if (scanning) return
        scanning = true
        updateStatus("Đang quét QR Wi-Fi...")
        speak("Đang quét mã QR.")
        scanner.decodeContinuous(barcodeCallback)
        scanner.resume()
    }

    private val barcodeCallback = BarcodeCallback { result ->
        val value = result.text?.trim().orEmpty()
        if (value.isEmpty()) return@BarcodeCallback
        if (!value.startsWith("WIFI:", true)) {
            updateStatus("QR không hợp lệ.")
            speak("Quét thất bại. Đây không phải mã Wi Fi.")
            return@BarcodeCallback
        }
        val config = parseWifiQr(value)
        if (config == null) {
            updateStatus("Không đọc được cấu trúc QR Wi-Fi.")
            speak("Quét thất bại. Không đọc được nội dung mã.")
            return@BarcodeCallback
        }
        scanner.pause()
        scanning = false
        val ok = connectWifiLegacy(config)
        if (ok) {
            updateStatus("Kết nối Wi-Fi thành công: ${config.ssid}")
            speak("Kết nối Wi Fi thành công.")
        } else {
            updateStatus("Kết nối Wi-Fi thất bại, vui lòng quét lại.")
            speak("Kết nối Wi Fi thất bại. Vui lòng thử lại.")
        }
    }

    private fun parseWifiQr(payload: String): WifiQrConfig? {
        // Expected: WIFI:T:WPA;S:ssid;P:password;H:false;;
        val body = payload.removePrefix("WIFI:")
        val entries = body.split(";")
        var ssid = ""
        var pass = ""
        var type = "WPA"
        for (entry in entries) {
            when {
                entry.startsWith("S:") -> ssid = entry.removePrefix("S:")
                entry.startsWith("P:") -> pass = entry.removePrefix("P:")
                entry.startsWith("T:") -> type = entry.removePrefix("T:")
            }
        }
        if (ssid.isBlank()) return null
        return WifiQrConfig(ssid, pass, type)
    }

    @Suppress("DEPRECATION")
    private fun connectWifiLegacy(cfg: WifiQrConfig): Boolean {
        val wifi = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
        if (!wifi.isWifiEnabled) {
            wifi.isWifiEnabled = true
            Thread.sleep(1200)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Android 10+ requires a different API; robot is API 24 so this is fallback safe.
            return false
        }

        val wc = WifiConfiguration().apply {
            SSID = "\"${cfg.ssid}\""
            status = WifiConfiguration.Status.ENABLED
            allowedKeyManagement.clear()
            if (cfg.type.equals("WPA", true) || cfg.type.equals("WPA2", true)) {
                preSharedKey = "\"${cfg.password}\""
                allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA_PSK)
            } else {
                allowedKeyManagement.set(WifiConfiguration.KeyMgmt.NONE)
            }
        }
        val netId = wifi.addNetwork(wc)
        if (netId < 0) return false
        wifi.disconnect()
        val enabled = wifi.enableNetwork(netId, true)
        val reconnected = wifi.reconnect()
        return enabled && reconnected
    }

    private fun isWifiConnected(): Boolean {
        val cm = getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    private fun hasRuntimePermissions(): Boolean {
        val camOk = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        val locOk = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        return camOk && locOk
    }

    private fun requestRuntimePermissions() {
        ActivityCompat.requestPermissions(
            this,
            arrayOf(Manifest.permission.CAMERA, Manifest.permission.ACCESS_FINE_LOCATION),
            1001,
        )
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 1001 && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            beginScanFlow()
        } else {
            updateStatus("Thiếu quyền camera/location để quét QR.")
            speak("Thiếu quyền để quét mã QR.")
        }
    }

    private fun updateStatus(text: String) {
        statusView.text = text
    }

    private fun speakBasicGuide() {
        speak(
            "Hướng dẫn nhanh. Bước một, mở camera trước mã QR Wi Fi. " +
                "Bước hai, giữ yên hai giây để robot đọc mạng. " +
                "Bước ba, chờ thông báo kết nối thành công rồi quay lại màn hình điều khiển.",
            utteranceId = "guide-intro",
        )
    }

    private fun requestVoicePriority() {
        val audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
        @Suppress("DEPRECATION")
        val result = audioManager.requestAudioFocus(
            null,
            AudioManager.STREAM_MUSIC,
            AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK,
        )
        focusGranted = result == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        if (focusGranted) {
            val maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            val targetVol = (maxVol * 0.85f).toInt().coerceAtLeast(1)
            audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, targetVol, 0)
        }
    }

    private fun releaseVoicePriority() {
        if (!focusGranted) return
        val audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
        @Suppress("DEPRECATION")
        audioManager.abandonAudioFocus(null)
        focusGranted = false
    }

    private fun speak(text: String, utteranceId: String = "wifi-provision-status") {
        if (speakViaRobotSdk(text, utteranceId)) {
            return
        }
        if (!ttsReady) {
            pendingSpeechQueue.add(text to utteranceId)
            return
        }
        speakNow(text, utteranceId, TextToSpeech.QUEUE_FLUSH)
    }

    private fun speakNow(text: String, utteranceId: String, queueMode: Int) {
        if (speakViaRobotSdk(text, utteranceId)) {
            return
        }
        requestVoicePriority()
        val params = Bundle().apply {
            putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f)
        }
        val speakResult = tts.speak(text, queueMode, params, utteranceId)
        Log.d(TAG, "tts.speak result=$speakResult utteranceId=$utteranceId text=$text")
        if (speakResult == TextToSpeech.ERROR) {
            updateStatus("Lỗi phát tiếng. Nhấn Nghe hướng dẫn để thử lại.")
        }
    }

    private fun speakViaRobotSdk(text: String, utteranceId: String): Boolean {
        return try {
            requestVoicePriority()
            SpeechApi.get().playTTs(text, object : TTsListener {
                override fun onTtsBegin() = Unit
                override fun onTtsVolumeChange(volume: Int) = Unit
                override fun onTtsCompleted() {
                    releaseVoicePriority()
                    if (utteranceId == "guide-intro" && waitingGuideThenScan) {
                        waitingGuideThenScan = false
                        runOnUiThread { beginScanFlow() }
                    }
                }

                override fun onError(code: Int, msg: String?) {
                    releaseVoicePriority()
                    Log.w(TAG, "SpeechApi.playTTs error code=$code msg=$msg")
                }
            })
            true
        } catch (e: Throwable) {
            Log.w(TAG, "SpeechApi.playTTs unavailable", e)
            false
        }
    }

    private fun initTts(forceDefault: Boolean = false) {
        ttsReady = false
        pendingInitStatus = null
        try {
            val createdTts = if (forceDefault) {
                TextToSpeech(this, this)
            } else {
                TextToSpeech(this, this, ROBOT_TTS_ENGINE)
            }
            tts = createdTts
            Log.d(TAG, "Init TTS requested. forceDefault=$forceDefault")
            pendingInitStatus?.let {
                pendingInitStatus = null
                handleTtsInit(it)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Init TTS exception", e)
            if (!forceDefault) {
                initTts(forceDefault = true)
            } else {
                updateStatus("Không khởi tạo được engine giọng nói.")
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        releaseVoicePriority()
        tts.stop()
        tts.shutdown()
    }

    data class WifiQrConfig(val ssid: String, val password: String, val type: String)
}
