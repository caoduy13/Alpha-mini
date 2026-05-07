package com.ubtech.alphaminivoiceapp

import android.util.Log
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * WebSocket client kết nối tới Alpha Mini Server /ws/chat.
 * Gửi: {"type":"chat","text":"..."}
 * Nhận: init, conversation, thinking, status, error
 */
class ChatWebSocket(private val serverIp: String, private val serverPort: Int = 8000) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .pingInterval(20, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    private val _status = MutableStateFlow<ServerStatus?>(null)
    val status: StateFlow<ServerStatus?> = _status.asStateFlow()

    val eventChannel = Channel<WsEvent>(Channel.UNLIMITED)

    enum class ConnectionState { DISCONNECTED, CONNECTING, CONNECTED }
    enum class WsEvent { CONNECTED, DISCONNECTED, ERROR }

    data class ChatMessage(val sender: String, val text: String, val emotion: String = "")
    data class ServerStatus(val aiReady: Boolean, val robotConnected: Boolean)

    private val wsUrl: String
        get() = "ws://$serverIp:$serverPort/ws/chat"

    fun connect() {
        if (_connectionState.value == ConnectionState.CONNECTED) return
        _connectionState.value = ConnectionState.CONNECTING

        val request = Request.Builder().url(wsUrl).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket connected")
                _connectionState.value = ConnectionState.CONNECTED
                eventChannel.trySend(WsEvent.CONNECTED)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleMessage(text)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                _connectionState.value = ConnectionState.DISCONNECTED
                eventChannel.trySend(WsEvent.DISCONNECTED)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket error: ${t.message}")
                _connectionState.value = ConnectionState.DISCONNECTED
                eventChannel.trySend(WsEvent.ERROR)
            }
        })
    }

    private fun handleMessage(text: String) {
        try {
            val json = JSONObject(text)
            val type = json.optString("type", "")

            when (type) {
                "init" -> {
                    val history = json.optJSONArray("history")
                    val list = mutableListOf<ChatMessage>()
                    if (history != null) {
                        for (i in 0 until history.length()) {
                            val obj = history.getJSONObject(i)
                            val role = obj.optString("role", "user")
                            val content = obj.optString("content", "")
                            list.add(ChatMessage(if (role == "user") "user" else "bot", content))
                        }
                    }
                    _messages.value = list.reversed()
                    val st = json.optJSONObject("status")
                    if (st != null) {
                        _status.value = ServerStatus(
                            aiReady = st.optBoolean("ai_ready", false),
                            robotConnected = st.optBoolean("robot_connected", false)
                        )
                    }
                }
                "conversation" -> {
                    val user = json.optString("user", "")
                    val bot = json.optString("bot", "")
                    if (user.isNotEmpty()) _messages.value = _messages.value + ChatMessage("user", user)
                    if (bot.isNotEmpty()) _messages.value = _messages.value + ChatMessage("bot", bot, json.optString("emotion", ""))
                }
                "thinking" -> {
                    // Có thể hiển thị "đang suy nghĩ..."
                }
                "status" -> {
                    _status.value = ServerStatus(
                        aiReady = json.optBoolean("ai_ready", false),
                        robotConnected = json.optBoolean("robot_connected", false)
                    )
                }
                "ping" -> {
                    sendPong()
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Parse message error: ${e.message}")
        }
    }

    fun sendChat(text: String) {
        val json = JSONObject().apply {
            put("type", "chat")
            put("text", text)
        }
        webSocket?.send(json.toString())
    }

    fun sendReset() {
        webSocket?.send(JSONObject().apply { put("type", "reset") }.toString())
    }

    fun sendRobotAction(action: String, text: String? = null, emotion: String? = null) {
        val json = JSONObject().apply {
            put("type", "robot_action")
            put("action", action)
            if (text != null) put("text", text)
            if (emotion != null) put("emotion", emotion)
        }
        webSocket?.send(json.toString())
    }

    fun sendPlayMusic(song: String) {
        webSocket?.send(JSONObject().apply {
            put("type", "play_music")
            put("song", song)
        }.toString())
    }

    fun sendStopMusic() {
        webSocket?.send(JSONObject().apply { put("type", "stop_music") }.toString())
    }

    private fun sendPong() {
        webSocket?.send(JSONObject().apply { put("type", "pong") }.toString())
    }

    fun disconnect() {
        webSocket?.close(1000, "Client close")
        webSocket = null
        _connectionState.value = ConnectionState.DISCONNECTED
    }

    companion object {
        private const val TAG = "ChatWebSocket"
    }
}
