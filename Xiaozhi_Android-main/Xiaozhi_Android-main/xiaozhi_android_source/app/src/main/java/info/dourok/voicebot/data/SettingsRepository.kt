package info.dourok.voicebot.data

import info.dourok.voicebot.data.model.MqttConfig
import info.dourok.voicebot.data.model.TransportType
import javax.inject.Inject
import javax.inject.Singleton

interface SettingsRepository {
    var transportType: TransportType
    var mqttConfig: MqttConfig?
    var webSocketUrl: String?
}

@Singleton
class SettingsRepositoryImpl @Inject constructor() : SettingsRepository {
    override var transportType: TransportType = TransportType.MQTT
    override var mqttConfig: MqttConfig? = null
    override var webSocketUrl: String? = null
}