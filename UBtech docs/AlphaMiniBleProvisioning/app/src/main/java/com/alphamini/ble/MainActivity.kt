package com.alphamini.ble

import android.Manifest
import android.os.Bundle
import android.os.Build
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BluetoothSearching
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
class MainActivity : ComponentActivity() {

    private val viewModel: ScanViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            MaterialTheme {
                val uiState by viewModel.uiState.collectAsState()
                val devices by viewModel.devices.collectAsState()
                val snackbarHostState = remember { SnackbarHostState() }
                val scope = rememberCoroutineScope()

                val requiredPermissions = remember {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                        arrayOf(
                            Manifest.permission.BLUETOOTH_SCAN,
                            Manifest.permission.BLUETOOTH_CONNECT
                        )
                    } else {
                        arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
                    }
                }

                var hasAllPermissions by remember {
                    mutableStateOf(
                        requiredPermissions.all { p ->
                            ContextCompat.checkSelfPermission(this@MainActivity, p) ==
                                android.content.pm.PackageManager.PERMISSION_GRANTED
                        }
                    )
                }

                val permissionLauncher =
                    rememberLauncherForActivityResult(
                        contract = ActivityResultContracts.RequestMultiplePermissions()
                    ) { results: Map<String, Boolean> ->
                        hasAllPermissions = requiredPermissions.all { results[it] == true }
                        if (!hasAllPermissions) {
                            scope.launch {
                                snackbarHostState.showSnackbar(
                                    "Cần cấp quyền Bluetooth để quét thiết bị."
                                )
                            }
                        }
                    }

                LaunchedEffect(Unit) {
                    viewModel.events.collectLatest { msg ->
                        scope.launch { snackbarHostState.showSnackbar(msg) }
                    }
                }

                Scaffold(
                    topBar = {
                        TopAppBar(
                            title = { Text("AlphaMini AI") },
                            navigationIcon = {
                                Icon(
                                    imageVector = Icons.Default.BluetoothSearching,
                                    contentDescription = null,
                                    modifier = Modifier.padding(start = 12.dp)
                                )
                            }
                        )
                    },
                    snackbarHost = { SnackbarHost(snackbarHostState) }
                ) { padding ->
                    Column(
                        modifier = Modifier
                            .padding(padding)
                            .fillMaxSize()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Text(
                            "Đây là app AlphaMini AI mới.\n" +
                                "Giao diện BLE provisioning cũ đã được ẩn.",
                            style = MaterialTheme.typography.bodyMedium
                        )

                        Button(
                            onClick = {
                                scope.launch {
                                    snackbarHostState.showSnackbar(
                                        "Ở bản tiếp theo, nút này sẽ mở màn hình chat AI với robot."
                                    )
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Mở Chat với Alpha Mini")
                        }
                    }
                }
            }
        }
    }
}

