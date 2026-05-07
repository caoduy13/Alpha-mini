package com.ubtech.alphaminivoiceapp

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import java.util.Locale

/**
 * Voice input qua Android SpeechRecognizer.
 * Hỗ trợ tiếng Việt và tiếng Anh.
 */
class VoiceInputHelper(private val context: Context) {

    private var speechRecognizer: SpeechRecognizer? = null
    private var onResult: ((String) -> Unit)? = null
    private var onError: ((String) -> Unit)? = null
    private var onListening: ((Boolean) -> Unit)? = null

    fun setCallbacks(
        onResult: (String) -> Unit,
        onError: (String) -> Unit,
        onListening: (Boolean) -> Unit
    ) {
        this.onResult = onResult
        this.onError = onError
        this.onListening = onListening
    }

    fun startListening() {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            onError?.invoke("Nhận diện giọng nói không khả dụng")
            return
        }

        speechRecognizer?.destroy()
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale("vi"))
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "vi")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }

        speechRecognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                onListening?.invoke(true)
            }
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {
                onListening?.invoke(false)
            }
            override fun onError(error: Int) {
                onListening?.invoke(false)
                val msg = when (error) {
                    SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Hết thời gian mạng"
                    SpeechRecognizer.ERROR_NETWORK -> "Lỗi mạng"
                    SpeechRecognizer.ERROR_AUDIO -> "Lỗi âm thanh"
                    SpeechRecognizer.ERROR_SERVER -> "Lỗi server"
                    SpeechRecognizer.ERROR_CLIENT -> "Lỗi client"
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Không nghe thấy giọng nói"
                    SpeechRecognizer.ERROR_NO_MATCH -> "Không nhận diện được"
                    else -> "Lỗi: $error"
                }
                onError?.invoke(msg)
            }
            override fun onResults(results: Bundle?) {
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val text = matches?.firstOrNull()?.trim()
                if (!text.isNullOrEmpty()) {
                    onResult?.invoke(text)
                } else {
                    onError?.invoke("Không nhận diện được")
                }
            }
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        speechRecognizer?.startListening(intent)
    }

    fun stopListening() {
        speechRecognizer?.stopListening()
        onListening?.invoke(false)
    }

    fun destroy() {
        speechRecognizer?.destroy()
        speechRecognizer = null
    }

    companion object {
        private const val TAG = "VoiceInputHelper"
    }
}
