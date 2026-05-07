package com.alphamini.setup.model

data class WifiNetwork(
    val ssid: String,
    val rssi: Int,
    val isSecured: Boolean,
    val isSaved: Boolean
)

