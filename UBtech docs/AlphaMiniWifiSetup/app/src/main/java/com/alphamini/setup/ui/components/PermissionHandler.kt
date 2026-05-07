package com.alphamini.setup.ui.components

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.window.DialogProperties
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.content.PermissionChecker

@Composable
fun WifiPermissionHandler(
    content: @Composable () -> Unit
) {
    val context = LocalContext.current
    val activity = remember(context) { context as? android.app.Activity }

    val permissions = remember {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            arrayOf(
                Manifest.permission.ACCESS_NETWORK_STATE,
                Manifest.permission.ACCESS_WIFI_STATE,
                Manifest.permission.NEARBY_WIFI_DEVICES
            )
        } else {
            arrayOf(
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION,
                Manifest.permission.ACCESS_WIFI_STATE,
                Manifest.permission.ACCESS_NETWORK_STATE
            )
        }
    }

    fun hasAllPermissions(): Boolean {
        return permissions.all {
            ContextCompat.checkSelfPermission(
                context,
                it
            ) == PermissionChecker.PERMISSION_GRANTED
        }
    }

    var showRationale by rememberSaveable { mutableStateOf(false) }
    var showSettingsDialog by rememberSaveable { mutableStateOf(false) }

    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { result ->
        val allGranted = result.values.all { it }
        if (!allGranted) {
            if (activity != null && permissions.any {
                    !ActivityCompat.shouldShowRequestPermissionRationale(activity, it) &&
                            ContextCompat.checkSelfPermission(context, it) != PermissionChecker.PERMISSION_GRANTED
                }
            ) {
                showSettingsDialog = true
            } else {
                showRationale = true
            }
        }
    }

    val hasAll by rememberUpdatedState(newValue = hasAllPermissions())

    LaunchedEffect(Unit) {
        if (!hasAllPermissions()) {
            launcher.launch(permissions)
        }
    }

    when {
        hasAll -> content()

        showRationale -> {
            AlertDialog(
                onDismissRequest = {},
                properties = DialogProperties(dismissOnClickOutside = false),
                title = { Text("Cần quyền truy cập WiFi") },
                text = {
                    Text(
                        "App cần quyền truy cập WiFi / vị trí để quét danh sách mạng xung quanh và cấu hình cho robot."
                    )
                },
                confirmButton = {
                    TextButton(onClick = {
                        showRationale = false
                        launcher.launch(permissions)
                    }) { Text("Cho phép") }
                },
                dismissButton = {
                    TextButton(onClick = { showRationale = false }) {
                        Text("Hủy")
                    }
                }
            )
        }

        showSettingsDialog -> {
            AlertDialog(
                onDismissRequest = {},
                properties = DialogProperties(dismissOnClickOutside = false),
                title = { Text("Cần mở quyền trong Cài đặt") },
                text = {
                    Text(
                        "Bạn đã từ chối quyền truy cập WiFi. Vui lòng mở Cài đặt → Quyền ứng dụng và bật lại quyền để tiếp tục."
                    )
                },
                confirmButton = {
                    TextButton(onClick = {
                        showSettingsDialog = false
                        val intent = Intent(
                            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                            Uri.fromParts("package", context.packageName, null)
                        )
                        context.startActivity(intent)
                    }) { Text("Mở Cài đặt") }
                },
                dismissButton = {
                    TextButton(onClick = { showSettingsDialog = false }) {
                        Text("Đóng")
                    }
                }
            )
        }
    }
}

