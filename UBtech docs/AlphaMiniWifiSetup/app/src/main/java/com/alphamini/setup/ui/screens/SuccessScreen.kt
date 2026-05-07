package com.alphamini.setup.ui.screens

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.alphamini.setup.viewmodel.WifiSetupViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SuccessScreen(
    viewModel: WifiSetupViewModel,
    onFinish: () -> Unit
) {
    val selectedWifi by viewModel.selectedWifi.collectAsState()

    var animTarget by remember { mutableStateOf(0.0f) }
    val scale by animateFloatAsState(targetValue = animTarget, label = "checkScale")

    LaunchedEffect(Unit) {
        animTarget = 1.0f
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Hoàn tất") }) }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(
                imageVector = Icons.Default.CheckCircle,
                contentDescription = "Thành công",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier
                    .size(96.dp)
                    .scale(scale)
            )

            Spacer(Modifier.height(24.dp))

            Text(
                text = "Robot đã kết nối WiFi thành công!",
                style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold)
            )

            Spacer(Modifier.height(12.dp))

            val ssid = selectedWifi?.ssid ?: "WiFi"
            Text(
                text = "Mạng: $ssid",
                style = MaterialTheme.typography.bodyLarge
            )

            Spacer(Modifier.height(24.dp))

            Text(
                text = "Vui lòng kết nối điện thoại về mạng WiFi \"$ssid\" để tiếp tục sử dụng các ứng dụng điều khiển robot.",
                style = MaterialTheme.typography.bodyMedium
            )

            Spacer(Modifier.height(32.dp))

            Button(onClick = onFinish) {
                Text("Hoàn tất")
            }
        }
    }
}

