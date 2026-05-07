package com.alphamini.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.callbackFlow

class BleManager(private val context: Context) {

    private val TAG = "BleManager"

    private val bluetoothManager: BluetoothManager? =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
    private val adapter: BluetoothAdapter? = bluetoothManager?.adapter

    private var bluetoothGatt: BluetoothGatt? = null

    // region Scan

    @SuppressLint("MissingPermission")
    fun scanDevices() = callbackFlow<BluetoothDevice> {
        val scanner: BluetoothLeScanner? = adapter?.bluetoothLeScanner
        if (scanner == null) {
            Log.e(TAG, "BluetoothLeScanner is null")
            close(IllegalStateException("Bluetooth scanner unavailable"))
            return@callbackFlow
        }

        if (adapter?.isEnabled != true) {
            Log.e(TAG, "Bluetooth is OFF")
            close(IllegalStateException("Bluetooth đang tắt. Hãy bật Bluetooth và thử lại."))
            return@callbackFlow
        }

        val callback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val device = result.device ?: return
                val name = device.name ?: return
                if (name.startsWith(BleConstants.NAME_PREFIX, ignoreCase = true)) {
                    trySend(device)
                }
            }

            override fun onScanFailed(errorCode: Int) {
                Log.e(TAG, "Scan failed: $errorCode")
                close()
            }
        }

        scanner.startScan(callback)
        val handler = Handler(Looper.getMainLooper())
        handler.postDelayed({
            scanner.stopScan(callback)
            close()
        }, BleConstants.SCAN_TIMEOUT_MS)

        awaitClose {
            try {
                scanner.stopScan(callback)
            } catch (_: Exception) {
            }
        }
    }

    // endregion

    // region Connect / GATT

    interface GattListener {
        fun onReady()
        fun onNotification(data: ByteArray)
        fun onDisconnected()
        fun onError(message: String)
    }

    private var gattListener: GattListener? = null

    @SuppressLint("MissingPermission")
    fun connect(address: String, listener: GattListener) {
        gattListener = listener
        val device = adapter?.getRemoteDevice(address)
        if (device == null) {
            listener.onError("Device not found")
            return
        }

        bluetoothGatt?.close()
        bluetoothGatt = null

        bluetoothGatt = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
        } else {
            device.connectGatt(context, false, gattCallback)
        }
    }

    private val gattCallback = object : BluetoothGattCallback() {

        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            super.onConnectionStateChange(gatt, status, newState)
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                Log.d(TAG, "Connected, requesting MTU ${BleConstants.MTU_SIZE}")
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                    gatt.requestMtu(BleConstants.MTU_SIZE)
                } else {
                    gatt.discoverServices()
                }
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                Log.d(TAG, "Disconnected")
                gattListener?.onDisconnected()
            }
        }

        override fun onMtuChanged(gatt: BluetoothGatt, mtu: Int, status: Int) {
            super.onMtuChanged(gatt, mtu, status)
            Log.d(TAG, "MTU changed: $mtu, status=$status")
            gatt.discoverServices()
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            super.onServicesDiscovered(gatt, status)
            if (status == BluetoothGatt.GATT_SUCCESS) {
                logServices(gatt)
                val service = gatt.getService(BleConstants.SERVICE_UUID)
                if (service != null) {
                    enableIndication(gatt)
                    gattListener?.onReady()
                } else {
                    gattListener?.onError(
                        "Không tìm thấy UBT Service: ${BleConstants.SERVICE_UUID}"
                    )
                }
            } else {
                gattListener?.onError("discoverServices failed: $status")
            }
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic
        ) {
            super.onCharacteristicChanged(gatt, characteristic)
            if (characteristic.uuid == BleConstants.CHAR_INDICATE_UUID) {
                val data = characteristic.value ?: return
                Log.d(TAG, "INDICATE: ${data.decodeToString()}")
                gattListener?.onNotification(data)
            }
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray
        ) {
            super.onCharacteristicChanged(gatt, characteristic, value)
            if (characteristic.uuid == BleConstants.CHAR_INDICATE_UUID) {
                Log.d(TAG, "INDICATE(33+): ${value.decodeToString()}")
                gattListener?.onNotification(value)
            }
        }
    }

    @SuppressLint("MissingPermission")
    private fun enableIndication(gatt: BluetoothGatt) {
        val service = gatt.getService(BleConstants.SERVICE_UUID)
        val char = service?.getCharacteristic(BleConstants.CHAR_INDICATE_UUID)
        if (char == null) {
            Log.w(TAG, "INDICATE characteristic not found")
            return
        }

        gatt.setCharacteristicNotification(char, true)

        val descriptor = char.getDescriptor(BleConstants.CLIENT_CONFIG_UUID)
        if (descriptor == null) {
            Log.w(TAG, "Descriptor 0x2902 not found")
            return
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            gatt.writeDescriptor(
                descriptor,
                BluetoothGattDescriptor.ENABLE_INDICATION_VALUE
            )
        } else {
            @Suppress("DEPRECATION")
            descriptor.value = BluetoothGattDescriptor.ENABLE_INDICATION_VALUE
            @Suppress("DEPRECATION")
            gatt.writeDescriptor(descriptor)
        }
        Log.d(TAG, "INDICATE enabled on ${BleConstants.CHAR_INDICATE_UUID}")
    }

    @SuppressLint("MissingPermission")
    fun write(packet: ByteArray): Boolean {
        val gatt = bluetoothGatt ?: run {
            Log.e(TAG, "GATT is null")
            return false
        }
        val service = gatt.getService(BleConstants.SERVICE_UUID) ?: run {
            Log.e(TAG, "Service not found")
            return false
        }
        val char = service.getCharacteristic(BleConstants.CHAR_WRITE_UUID) ?: run {
            Log.e(TAG, "Write characteristic not found")
            return false
        }

        Log.d(TAG, "Writing ${packet.size} bytes")

        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val result = gatt.writeCharacteristic(
                char,
                packet,
                BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
            )
            result == BluetoothStatusCodes.SUCCESS
        } else {
            @Suppress("DEPRECATION")
            char.value = packet
            @Suppress("DEPRECATION")
            gatt.writeCharacteristic(char)
        }
    }

    @SuppressLint("MissingPermission")
    fun write(json: String): Boolean {
        val bytes = json.toByteArray(Charsets.UTF_8)
        Log.d(TAG, "Writing JSON (${bytes.size} bytes): $json")
        return write(bytes)
    }

    @SuppressLint("MissingPermission")
    fun disconnect() {
        try {
            bluetoothGatt?.disconnect()
            bluetoothGatt?.close()
        } catch (_: Exception) {
        } finally {
            bluetoothGatt = null
        }
    }

    private fun logServices(gatt: BluetoothGatt) {
        gatt.services?.forEach { svc ->
            Log.d(TAG, "Service: ${svc.uuid}")
            svc.characteristics.forEach { ch ->
                Log.d(TAG, "  Char: ${ch.uuid} props=${ch.properties}")
            }
        }
    }
}

