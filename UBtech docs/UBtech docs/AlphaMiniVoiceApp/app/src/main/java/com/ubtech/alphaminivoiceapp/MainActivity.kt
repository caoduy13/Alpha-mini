package com.ubtech.alphaminivoiceapp

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.ubtech.alphaminivoiceapp.databinding.ActivityMainBinding
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var chatWs: ChatWebSocket? = null
    private var voiceHelper: VoiceInputHelper? = null
    private var connectionJob: Job? = null
    private var messagesJob: Job? = null
    private var serverIp: String = ""
    private var serverPort: Int = 8000

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { granted ->
        if (granted.values.any { !it }) {
            Toast.makeText(this, "Cần quyền microphone để dùng giọng nói", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        requestPermissions()
        setupRecyclerView()
        setupClickListeners()
        setupVoiceHelper()
        updateConnectionUi(ChatWebSocket.ConnectionState.DISCONNECTED)
    }

    private fun requestPermissions() {
        val perms = arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.INTERNET,
            Manifest.permission.ACCESS_NETWORK_STATE
        )
        if (perms.any { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }) {
            permissionLauncher.launch(perms)
        }
    }

    private fun setupRecyclerView() {
        val adapter = ChatAdapter(mutableListOf())
        binding.recyclerChat.layoutManager = LinearLayoutManager(this).apply {
            stackFromEnd = true
        }
        binding.recyclerChat.adapter = adapter
    }

    private fun setupClickListeners() {
        binding.btnDiscover.setOnClickListener { discoverAndConnect() }
        binding.btnConnect.setOnClickListener { connectManual() }
        binding.btnSend.setOnClickListener { sendText() }
        binding.btnVoice.setOnClickListener { toggleVoice() }
        binding.btnReset.setOnClickListener { chatWs?.sendReset() }
        binding.btnDance.setOnClickListener { chatWs?.sendPlayMusic("sexy love") }
        binding.btnStopMusic.setOnClickListener { chatWs?.sendStopMusic() }
        binding.btnWave.setOnClickListener { chatWs?.sendRobotAction("emotion", null, "wave") }
    }

    private fun setupVoiceHelper() {
        voiceHelper = VoiceInputHelper(this).apply {
            setCallbacks(
                onResult = { text ->
                    runOnUiThread {
                        binding.inputText.setText(text)
                        sendText()
                    }
                },
                onError = { msg ->
                    runOnUiThread { Toast.makeText(this@MainActivity, msg, Toast.LENGTH_SHORT).show() }
                },
                onListening = { listening ->
                    runOnUiThread {
                        binding.btnVoice.text = if (listening) "⏹ Dừng" else "🎤 Nói"
                        binding.btnVoice.isSelected = listening
                    }
                }
            )
        }
    }

    private var isListening = false
    private fun toggleVoice() {
        isListening = !isListening
        if (isListening) {
            voiceHelper?.startListening()
        } else {
            voiceHelper?.stopListening()
        }
    }

    private fun discoverAndConnect() {
        binding.statusText.text = "Đang tìm server..."
        binding.btnDiscover.isEnabled = false
        lifecycleScope.launch {
            val info = ServerDiscovery.discover()
            runOnUiThread {
                binding.btnDiscover.isEnabled = true
                if (info != null) {
                    serverIp = info.ip
                    serverPort = info.port
                    binding.inputServerIp.setText(serverIp)
                    binding.inputServerPort.setText(serverPort.toString())
                    binding.statusText.text = "Tìm thấy: ${info.name} @ $serverIp:$serverPort"
                    connect()
                } else {
                    binding.statusText.text = "Không tìm thấy server. Nhập IP thủ công."
                }
            }
        }
    }

    private fun connectManual() {
        serverIp = binding.inputServerIp.text.toString().trim()
        serverPort = binding.inputServerPort.text.toString().toIntOrNull() ?: 8000
        if (serverIp.isEmpty()) {
            Toast.makeText(this, "Nhập IP server", Toast.LENGTH_SHORT).show()
            return
        }
        connect()
    }

    private fun connect() {
        connectionJob?.cancel()
        messagesJob?.cancel()
        chatWs?.disconnect()
        chatWs = ChatWebSocket(serverIp, serverPort)
        messagesJob = lifecycleScope.launch {
            chatWs!!.messages.collectLatest { list ->
                runOnUiThread {
                    (binding.recyclerChat.adapter as? ChatAdapter)?.update(list)
                    if (list.isNotEmpty()) binding.recyclerChat.scrollToPosition(list.size - 1)
                }
            }
        }
        connectionJob = lifecycleScope.launch {
            chatWs!!.connectionState.collectLatest { state ->
                runOnUiThread { updateConnectionUi(state) }
            }
        }
        chatWs!!.connect()
        binding.statusText.text = "Đang kết nối..."
    }

    private fun updateConnectionUi(state: ChatWebSocket.ConnectionState) {
        when (state) {
            ChatWebSocket.ConnectionState.CONNECTED -> {
                binding.statusText.text = "Đã kết nối"
                binding.btnConnect.isEnabled = false
                binding.btnSend.isEnabled = true
                binding.btnVoice.isEnabled = true
                binding.btnReset.isEnabled = true
                binding.btnDance.isEnabled = true
                binding.btnStopMusic.isEnabled = true
                binding.btnWave.isEnabled = true
            }
            ChatWebSocket.ConnectionState.CONNECTING ->
                binding.statusText.text = "Đang kết nối..."
            ChatWebSocket.ConnectionState.DISCONNECTED -> {
                binding.statusText.text = "Chưa kết nối"
                binding.btnConnect.isEnabled = true
                binding.btnSend.isEnabled = false
                binding.btnVoice.isEnabled = false
                binding.btnReset.isEnabled = false
                binding.btnDance.isEnabled = false
                binding.btnStopMusic.isEnabled = false
                binding.btnWave.isEnabled = false
            }
        }
    }

    private fun sendText() {
        val text = binding.inputText.text.toString().trim()
        if (text.isEmpty()) return
        chatWs?.sendChat(text)
        binding.inputText.setText("")
    }

    override fun onDestroy() {
        chatWs?.disconnect()
        voiceHelper?.destroy()
        super.onDestroy()
    }
}
