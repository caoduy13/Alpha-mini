package com.alphamini.setup.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.alphamini.setup.model.WifiNetwork
import com.alphamini.setup.ui.components.WifiPermissionHandler
import com.alphamini.setup.ui.components.WifiSignalIcon
import com.alphamini.setup.viewmodel.UiState
import com.alphamini.setup.viewmodel.WifiSetupViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WifiScanScreen(
    viewModel: WifiSetupViewModel,
    onWifiSelected: () -> Unit
) {
    val wifiList by viewModel.wifiList.collectAsState()
    val uiState by viewModel.uiState.collectAsState()
    val error by viewModel.errorMessage.collectAsState()

    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    LaunchedEffect(error) {
        error?.let {
            scope.launch {
                snackbarHostState.showSnackbar(it)
                viewModel.clearError()
            }
        }
    }

    WifiPermissionHandler {
        Scaffold(
            topBar = {
                TopAppBar(title = { Text("Chọn mạng WiFi cho robot") })
            },
            snackbarHost = { SnackbarHost(hostState = snackbarHostState) }
        ) { padding ->
            Column(
                modifier = Modifier
                    .padding(padding)
                    .fillMaxSize()
                    .padding(16.dp)
            ) {
                Text(
                    text = "Đảm bảo điện thoại đã kết nối vào hotspot AlphaMini-XXXX",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.8f)
                )

                Spacer(Modifier.height(16.dp))

                ElevatedButton(
                    onClick = { viewModel.scanWifi() },
                    enabled = uiState != UiState.SCANNING
                ) {
                    Text(
                        if (uiState == UiState.SCANNING) "Đang quét WiFi..." else "Quét WiFi"
                    )
                }

                Spacer(Modifier.height(16.dp))

                when {
                    uiState == UiState.SCANNING && wifiList.isEmpty() -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("Đang quét mạng WiFi xung quanh…")
                        }
                    }

                    wifiList.isEmpty() -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("Chưa có mạng nào. Thử quét lại.")
                        }
                    }

                    else -> {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            items(wifiList) { wifi ->
                                WifiItemCard(
                                    wifi = wifi,
                                    onClick = {
                                        viewModel.selectWifi(wifi)
                                        onWifiSelected()
                                    }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun WifiItemCard(
    wifi: WifiNetwork,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            WifiSignalIcon(rssi = wifi.rssi, modifier = Modifier.size(24.dp))

            Spacer(Modifier.width(16.dp))

            Column(
                modifier = Modifier.weight(1f)
            ) {
                Text(
                    text = wifi.ssid,
                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold)
                )
                if (wifi.isSaved) {
                    Text(
                        text = "Đã lưu trên điện thoại",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }

            if (wifi.isSecured) {
                Text(
                    text = "Có mật khẩu",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                )
            } else {
                Text(
                    text = "Mở",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary
                )
            }
        }
    }
}

