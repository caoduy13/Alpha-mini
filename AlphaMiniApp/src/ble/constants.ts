export const BLE = {
  SERVICE_UUID: '10057e66-28bd-4c3e-a030-08b4982739bc',
  CHAR_WRITE_UUID: 'd2f9ff26-ad08-4bd3-8436-9b8f33bdea76',
  CHAR_INDICATE_UUID: '7e0dffa2-c44f-48ac-a39e-3fce46d9aabb',
  CLIENT_CONFIG_UUID: '00002902-0000-1000-8000-00805f9b34fb',
  NAME_PREFIX: 'MINI_',
  SCAN_TIMEOUT_MS: 15000,
  CONNECT_TIMEOUT_MS: 15000,
  HANDSHAKE_TIMEOUT_MS: 10000,
  /** Wait for {"co":104} after {"co":4}; continue without it (co=2 does not depend on it). */
  READY_TIMEOUT_MS: 10000,
  /** Robot's own connect timer is 60 s, then it checks Internet access (docs/ble-protocol.md §13.3). */
  RESPONSE_TIMEOUT_MS: 90000,
  MTU_SIZE: 512,
} as const;
