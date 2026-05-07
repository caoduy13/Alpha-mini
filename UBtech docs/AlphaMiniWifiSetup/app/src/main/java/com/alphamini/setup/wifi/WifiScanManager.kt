package com.alphamini.setup.wifi

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.wifi.ScanResult
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiManager
import android.os.Build
import androidx.core.content.ContextCompat
import com.alphamini.setup.model.WifiNetwork
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext

class WifiScanManager(
    private val context: Context,
    private val scope: CoroutineScope
) {

    private val wifiManager: WifiManager =
        context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager

    private var lastScanTime: Long = 0L
    private var lastResults: List<WifiNetwork> = emptyList()

    suspend fun scan(): Result<List<WifiNetwork>> = withContext(Dispatchers.IO) {
        if (!hasScanPermission()) {
            return@withContext Result.failure(SecurityException("Missing WiFi scan permissions"))
        }

        val now = System.currentTimeMillis()
        if (now - lastScanTime <= 30_000 && lastResults.isNotEmpty()) {
            return@withContext Result.success(lastResults)
        }

        val flow = callbackFlow<List<ScanResult>> {
            val receiver = object : BroadcastReceiver() {
                override fun onReceive(c: Context?, intent: Intent?) {
                    if (intent?.action == WifiManager.SCAN_RESULTS_AVAILABLE_ACTION) {
                        trySend(wifiManager.scanResults)
                    }
                }
            }
            context.registerReceiver(
                receiver,
                IntentFilter(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION)
            )

            val started = wifiManager.startScan()
            if (!started) {
                trySend(wifiManager.scanResults)
            }

            awaitClose {
                try {
                    context.unregisterReceiver(receiver)
                } catch (_: Exception) {
                }
            }
        }

        val rawResults = try {
            flow.first()
        } catch (e: Exception) {
            wifiManager.scanResults
        }

        val configured = getConfiguredSsids()

        val networks = rawResults
            .filter { it.SSID.isNotBlank() && !it.SSID.contains("AlphaMini", ignoreCase = true) }
            .groupBy { it.SSID }
            .map { (ssid, list) ->
                val strongest = list.maxByOrNull { it.level }!!
                val caps = strongest.capabilities ?: ""
                val isSecured = caps.contains("WPA", true) ||
                        caps.contains("WEP", true) ||
                        caps.contains("WPA2", true) ||
                        caps.contains("WPA3", true)
                WifiNetwork(
                    ssid = ssid,
                    rssi = strongest.level,
                    isSecured = isSecured,
                    isSaved = configured.contains(ssid)
                )
            }
            .sortedByDescending { it.rssi }

        lastScanTime = now
        lastResults = networks

        Result.success(networks)
    }

    private fun hasScanPermission(): Boolean {
        val ctx = context.applicationContext
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                ctx,
                Manifest.permission.NEARBY_WIFI_DEVICES
            ) == PackageManager.PERMISSION_GRANTED
        } else {
            ContextCompat.checkSelfPermission(
                ctx,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED
        }
    }

    @Suppress("DEPRECATION")
    private fun getConfiguredSsids(): Set<String> {
        return try {
            val configured: List<WifiConfiguration>? = wifiManager.configuredNetworks
            configured
                ?.mapNotNull { it.SSID?.trim('"') }
                ?.toSet()
                ?: emptySet()
        } catch (_: SecurityException) {
            emptySet()
        } catch (_: Exception) {
            emptySet()
        }
    }
}

