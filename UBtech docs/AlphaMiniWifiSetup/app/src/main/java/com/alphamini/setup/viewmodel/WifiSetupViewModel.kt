package com.alphamini.setup.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.alphamini.setup.model.WifiNetwork
import com.alphamini.setup.wifi.ProvisioningRepository
import com.alphamini.setup.wifi.WifiScanManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class UiState {
    IDLE, SCANNING, READY, SENDING, SUCCESS, ERROR
}

class WifiSetupViewModel(app: Application) : AndroidViewModel(app) {

    private val scanManager = WifiScanManager(app.applicationContext, viewModelScope)
    private val provisioningRepository = ProvisioningRepository()

    private val _wifiList = MutableStateFlow<List<WifiNetwork>>(emptyList())
    val wifiList: StateFlow<List<WifiNetwork>> = _wifiList.asStateFlow()

    private val _selectedWifi = MutableStateFlow<WifiNetwork?>(null)
    val selectedWifi: StateFlow<WifiNetwork?> = _selectedWifi.asStateFlow()

    private val _uiState = MutableStateFlow(UiState.IDLE)
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    fun scanWifi() {
        _uiState.value = UiState.SCANNING
        _errorMessage.value = null
        viewModelScope.launch {
            val result = scanManager.scan()
            result
                .onSuccess {
                    _wifiList.value = it
                    _uiState.value = UiState.READY
                }
                .onFailure { e ->
                    _errorMessage.value = "Không quét được WiFi: ${e.message ?: "Lỗi không rõ"}"
                    _uiState.value = UiState.ERROR
                }
        }
    }

    fun selectWifi(wifi: WifiNetwork) {
        _selectedWifi.value = wifi
        if (_uiState.value == UiState.IDLE) {
            _uiState.value = UiState.READY
        }
    }

    fun sendConfig(password: String) {
        val wifi = _selectedWifi.value ?: return
        if (password.isBlank()) return

        _uiState.value = UiState.SENDING
        _errorMessage.value = null

        viewModelScope.launch {
            val result = provisioningRepository.sendWifiConfig(wifi.ssid, password)
            result
                .onSuccess {
                    _uiState.value = UiState.SUCCESS
                }
                .onFailure { e ->
                    _errorMessage.value =
                        "Không gửi được, kiểm tra kết nối hotspot.\n${e.message ?: ""}"
                    _uiState.value = UiState.ERROR
                }
        }
    }

    fun clearError() {
        _errorMessage.value = null
        if (_uiState.value == UiState.ERROR) {
            _uiState.value = UiState.READY
        }
    }
}

