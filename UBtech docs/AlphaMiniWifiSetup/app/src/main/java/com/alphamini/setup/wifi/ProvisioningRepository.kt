package com.alphamini.setup.wifi

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class ProvisioningRepository {

    companion object {
        const val ROBOT_AP_IP = "192.168.4.1"
        private const val ENDPOINT = "http://$ROBOT_AP_IP/provision"
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    }

    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    suspend fun sendWifiConfig(ssid: String, password: String): Result<Unit> =
        withContext(Dispatchers.IO) {
            val bodyJson = JSONObject().apply {
                put("ssid", ssid)
                put("password", password)
                put("cmd", "wifi_config")
            }
            val body = bodyJson.toString().toRequestBody(JSON_MEDIA_TYPE)

            suspend fun doRequest(): Result<Unit> {
                val request = Request.Builder()
                    .url(ENDPOINT)
                    .header("Content-Type", "application/json")
                    .post(body)
                    .build()

                return try {
                    client.newCall(request).execute().use { response ->
                        if (!response.isSuccessful) {
                            return@use Result.failure<Unit>(
                                RuntimeException("HTTP ${response.code}")
                            )
                        }
                        val respStr = response.body?.string().orEmpty()
                        val json = try {
                            JSONObject(respStr)
                        } catch (_: Exception) {
                            JSONObject().put("status", "error")
                        }
                        val status = json.optString("status", "error")
                        if (status.equals("ok", ignoreCase = true)) {
                            Result.success(Unit)
                        } else {
                            Result.failure(
                                RuntimeException(
                                    json.optString("message", "Robot returned status=$status")
                                )
                            )
                        }
                    }
                } catch (e: Exception) {
                    Result.failure(e)
                }
            }

            val first = doRequest()
            if (first.isSuccess) return@withContext first

            delay(1000)
            val second = doRequest()
            if (second.isSuccess) second else first
        }
}

