package com.alphamini.setup.navigation

sealed class Screen(val route: String) {
    data object WifiScan : Screen("wifi_scan")
    data object Password : Screen("password")
    data object Success : Screen("success")
}

