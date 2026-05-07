package com.alphamini.ble

import android.app.Application
import android.bluetooth.BluetoothDevice
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch

data class BleDeviceItem(
    val name: String,
    val address: String
)

enum class ScanUiState {
    Idle, Scanning, Connected
}

class ScanViewModel(app: Application) : AndroidViewModel(app) {

    private val bleManager = BleManager(app.applicationContext)

    private val _devices = MutableStateFlow<List<BleDeviceItem>>(emptyList())
    val devices: StateFlow<List<BleDeviceItem>> = _devices.asStateFlow()

    private val _uiState = MutableStateFlow(ScanUiState.Idle)
    val uiState: StateFlow<ScanUiState> = _uiState.asStateFlow()

    private val _events = Channel<String>(Channel.BUFFERED)
    val events = _events.receiveAsFlow()

    fun startScan(context: Context) {
        _uiState.value = ScanUiState.Scanning
        _devices.value = emptyList()

        viewModelScope.launch {
            try {
                bleManager.scanDevices().collect { dev: BluetoothDevice ->
                    val current = _devices.value.toMutableList()
                    if (current.none { it.address == dev.address }) {
                        val name = dev.name ?: "Unknown"
                        current.add(BleDeviceItem(name, dev.address))
                        _devices.value = current
                    }
                }
            } catch (e: Exception) {
                _events.send("Lỗi scan: ${e.message}")
            } finally {
                _uiState.value = ScanUiState.Idle
            }
        }
    }

    fun connectTo(context: Context, address: String) {
        _uiState.value = ScanUiState.Connected
        viewModelScope.launch {
            _events.send("Kết nối GATT tới $address ...")
        }
        bleManager.connect(address, object : BleManager.GattListener {
            override fun onReady() {
                viewModelScope.launch {
                    _events.send("✓ GATT sẵn sàng (INDICATE đã bật)")
                }
            }

            override fun onNotification(data: ByteArray) {
                val text = runCatching { data.decodeToString() }.getOrElse { "<binary>" }
                viewModelScope.launch {
                    _events.send("← $text")
                }
            }

            override fun onDisconnected() {
                _uiState.value = ScanUiState.Idle
                viewModelScope.launch {
                    _events.send("BLE bị ngắt kết nối")
                }
            }

            override fun onError(message: String) {
                _uiState.value = ScanUiState.Idle
                viewModelScope.launch {
                    _events.send("Lỗi GATT: $message")
                }
            }
        })
    }

    fun sendAuth() {
        viewModelScope.launch {
            val packet = BleProtocol.buildAuthPacket()
            val ok = bleManager.write(packet)
            if (ok) {
                _events.send("→ Gửi gói auth")
            } else {
                _events.send("Gửi gói auth thất bại (GATT chưa sẵn sàng?)")
            }
        }
    }

    fun sendWifiConfig(ssid: String, password: String) {
        viewModelScope.launch {
            val json = """
                {
                  "cmd": "wifi_config",
                  "ssid": "$ssid",
                  "password": "$password"
                }
            """.trimIndent()
            val ok = bleManager.write(json)
            if (ok) {
                _events.send("→ Gửi wifi_config (JSON thuần)")
            } else {
                _events.send("Gửi wifi_config thất bại (GATT chưa sẵn sàng?)")
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        bleManager.disconnect()
    }
}

