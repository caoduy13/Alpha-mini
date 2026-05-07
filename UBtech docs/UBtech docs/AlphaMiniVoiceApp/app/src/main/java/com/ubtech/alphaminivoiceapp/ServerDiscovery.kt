package com.ubtech.alphaminivoiceapp

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.nio.charset.StandardCharsets

/**
 * UDP Discovery — tìm Alpha Mini Server trong mạng LAN.
 * Server phát trên port 54545, magic "ALPHAMINI_DISCOVER".
 * Trả về JSON: {"name":"...","ip":"...","port":8000}
 */
object ServerDiscovery {
    private const val TAG = "ServerDiscovery"
    private const val DISCOVERY_PORT = 54545
    private const val MAGIC = "ALPHAMINI_DISCOVER"
    private const val TIMEOUT_MS = 3000

    data class ServerInfo(val name: String, val ip: String, val port: Int)

    suspend fun discover(): ServerInfo? = withContext(Dispatchers.IO) {
        var socket: DatagramSocket? = null
        try {
            socket = DatagramSocket()
            socket.soTimeout = TIMEOUT_MS
            socket.broadcast = true

            val magicBytes = MAGIC.toByteArray(StandardCharsets.UTF_8)
            val broadcastAddr = InetAddress.getByName("255.255.255.255")
            val sendPacket = DatagramPacket(magicBytes, magicBytes.size, broadcastAddr, DISCOVERY_PORT)
            socket.send(sendPacket)

            val buffer = ByteArray(512)
            val recvPacket = DatagramPacket(buffer, buffer.size)
            socket.receive(recvPacket)

            val response = String(recvPacket.data, 0, recvPacket.length, StandardCharsets.UTF_8)
            Log.d(TAG, "Discovery response: $response")

            val json = org.json.JSONObject(response)
            ServerInfo(
                name = json.optString("name", "Alpha Mini Server"),
                ip = json.optString("ip", recvPacket.address.hostAddress ?: ""),
                port = json.optInt("port", 8000)
            )
        } catch (e: Exception) {
            Log.w(TAG, "Discovery failed: ${e.message}")
            null
        } finally {
            socket?.close()
        }
    }
}
