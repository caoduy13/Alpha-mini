package com.alphamini.ble

import java.util.UUID

object BleConstants {

    // UUID THỰC CỦA ALPHA MINI — xác nhận từ nRF Connect
    // Device: MINI_EAA0...00012017 | MAC: 62:12:99:E2:14:8C

    val SERVICE_UUID: UUID = UUID.fromString(
        "10057e66-28bd-4c3e-a030-08b4982739bc"
    )

    // Characteristic để GỬI command/data từ app → robot (READ + WRITE)
    val CHAR_WRITE_UUID: UUID = UUID.fromString(
        "d2f9ff26-ad08-4bd3-8436-9b8f33bdea76"
    )

    // Characteristic để NHẬN response từ robot → app (INDICATE, không phải NOTIFY)
    val CHAR_INDICATE_UUID: UUID = UUID.fromString(
        "7e0dffa2-c44f-48ac-a39e-3fce46d9aabb"
    )

    // Descriptor 0x2902 để enable INDICATE
    val CLIENT_CONFIG_UUID: UUID = UUID.fromString(
        "00002902-0000-1000-8000-00805f9b34fb"
    )

    // Filter tên thiết bị khi scan: bắt đầu bằng "MINI_"
    const val NAME_PREFIX = "MINI_"

    const val SCAN_TIMEOUT_MS: Long = 15_000L
    const val CONNECT_TIMEOUT_MS: Long = 15_000L
    const val RESPONSE_TIMEOUT_MS: Long = 30_000L
    const val MTU_SIZE: Int = 512
}

