package com.alphamini.setup.ui.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color

@Composable
fun WifiSignalIcon(rssi: Int, modifier: Modifier = Modifier) {
    val alpha = when {
        rssi >= -50 -> 1.0f
        rssi >= -60 -> 0.85f
        rssi >= -70 -> 0.7f
        else -> 0.55f
    }

    val color = MaterialTheme.colorScheme.primary.copy(alpha = alpha)

    Icon(
        imageVector = Icons.Filled.Wifi,
        contentDescription = "Cường độ WiFi",
        tint = color,
        modifier = modifier
    )
}


