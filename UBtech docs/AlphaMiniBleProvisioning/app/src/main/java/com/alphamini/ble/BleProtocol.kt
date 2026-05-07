package com.alphamini.ble

import android.util.Base64
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.spec.SecretKeySpec
import kotlin.random.Random

object BleProtocol {

    private const val USER_ID = "alphamini_user"
    private const val AES_KEY = "ubt_alphamini_16"

    private const val METHOD_AUTH: Byte = 0x01
    private const val METHOD_WIFI_CONFIG: Byte = 0x02

    fun buildAuthPacket(): ByteArray {
        val salt = randomSalt(8)
        val md5Input = (USER_ID + salt).toByteArray(Charsets.UTF_8)
        val md5 = md5(md5Input)
        val encrypted = aesEncrypt(md5)
        val token = Base64.encodeToString(encrypted, Base64.NO_WRAP)

        val json = """
            {
              "VersionCode": 1,
              "EncryAlgorithm": "AES128",
              "UserId": "$USER_ID",
              "salt": "$salt",
              "token": "$token"
            }
        """.trimIndent()

        return frame(METHOD_AUTH, json)
    }

    fun buildWifiConfigPacket(ssid: String, password: String): ByteArray {
        val json = """
            {
              "cmd": "wifi_config",
              "ssid": "$ssid",
              "password": "$password"
            }
        """.trimIndent()

        return frame(METHOD_WIFI_CONFIG, json)
    }

    private fun frame(method: Byte, payloadJson: String): ByteArray {
        val payloadBytes = payloadJson.toByteArray(Charsets.UTF_8)
        val totalLen = 1 + payloadBytes.size
        val buffer = ByteBuffer.allocate(4 + totalLen).order(ByteOrder.BIG_ENDIAN)
        buffer.putInt(totalLen)
        buffer.put(method)
        buffer.put(payloadBytes)
        return buffer.array()
    }

    private fun randomSalt(length: Int): String {
        val chars = "abcdefghijklmnopqrstuvwxyz0123456789"
        val sb = StringBuilder(length)
        repeat(length) {
            sb.append(chars[Random.nextInt(chars.length)])
        }
        return sb.toString()
    }

    private fun md5(input: ByteArray): ByteArray {
        val md = MessageDigest.getInstance("MD5")
        return md.digest(input)
    }

    private fun aesEncrypt(input: ByteArray): ByteArray {
        val keyBytes = AES_KEY.toByteArray(Charsets.UTF_8)
        val keySpec = SecretKeySpec(keyBytes, "AES")
        val cipher = Cipher.getInstance("AES/ECB/PKCS5Padding")
        cipher.init(Cipher.ENCRYPT_MODE, keySpec)
        return cipher.doFinal(input)
    }
}

