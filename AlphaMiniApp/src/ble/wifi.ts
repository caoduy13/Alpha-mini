/**
 * JSON carried in BindOrSwitchWifiRequest/Response.data (docs/ble-protocol.md §13).
 * The robot switches on the integer key "co".
 */

export const WIFI_CO = {
  WIFI_LIST: 1,
  WIFI_CONFIG: 2,
  START_NETWORK_CONFIG: 4,
  QUIT_NETWORK_CONFIG: 12,
  ERROR: -1,
  WIFI_LIST_TO_MOBILE: 101,
  WIFI_CONNECTED: 102,
  READY: 104,
} as const;

export const WIFI_EC = {
  CONNECT_FAILED: 0,
  WRONG_PASSWORD: 1,
  PING_ERROR: 2,
  TVS_LOGIN_ERROR: 3,
  CONNECT_TIMEOUT: 4,
  ALREADY_CONNECTED: 5,
  TVS_ERROR: 6,
  ERROR_4G: 7,
  ERROR_4G_NO_SIM: 8,
  NEED_WEB_LOGIN: 11,
  NO_INTERNET: 12,
  CANNOT_CONNECT: 13,
  OTHER_DEVICE: 14,
} as const;

export function startNetworkConfigJson(): string {
  return JSON.stringify({ co: WIFI_CO.START_NETWORK_CONFIG });
}

export function quitNetworkConfigJson(): string {
  return JSON.stringify({ co: WIFI_CO.QUIT_NETWORK_CONFIG });
}

/**
 * Robot security selection only distinguishes open (empty password), WEP and WPA-PSK, so a
 * user-typed password is sent as "WPA2" and an empty one as "N" (scan-list spelling).
 */
export function capabilitiesFor(password: string): string {
  return password ? 'WPA2' : 'N';
}

/** Key order matches the SDK's Gson output (s, c, p, b, v, co); BSSID omitted when unknown. */
export function wifiConfigJson(params: {
  ssid: string;
  password: string;
  capabilities?: string;
  bssid?: string;
  dontPingNet?: '0' | '1';
}): string {
  const body: Record<string, string | number> = {
    s: params.ssid,
    c: params.capabilities ?? capabilitiesFor(params.password),
    p: params.password,
  };
  if (params.bssid) {
    body.b = params.bssid;
  }
  body.v = params.dontPingNet ?? '0';
  body.co = WIFI_CO.WIFI_CONFIG;
  return JSON.stringify(body);
}

export type WifiNotification = {
  co: number;
  ec?: number;
  cd?: string;
  /** Number of networks in a co=101 list push; SSIDs are deliberately not exposed. */
  networkCount?: number;
};

export function parseWifiNotification(data: string): WifiNotification | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== 'object') {
    return null;
  }
  const p = parsed as Record<string, unknown>;
  const co = Number(p.co);
  if (!Number.isInteger(co)) {
    return null;
  }
  const out: WifiNotification = { co };
  if (p.ec !== undefined && Number.isInteger(Number(p.ec))) {
    out.ec = Number(p.ec);
  }
  if (p.cd !== undefined && p.cd !== null) {
    out.cd = String(p.cd);
  }
  if (co === WIFI_CO.WIFI_LIST_TO_MOBILE && typeof p.p === 'string') {
    try {
      const list: unknown = JSON.parse(p.p);
      out.networkCount = Array.isArray(list) ? list.length : undefined;
    } catch {
      /* count unknown */
    }
  }
  return out;
}

export function wifiErrorMessage(ec: number | undefined): string {
  switch (ec) {
    case WIFI_EC.WRONG_PASSWORD:
      return 'Sai mật khẩu Wi-Fi, vui lòng nhập lại.';
    case WIFI_EC.CONNECT_FAILED:
    case WIFI_EC.CANNOT_CONNECT:
      return 'Robot không kết nối được Wi-Fi. Kiểm tra tên mạng (SSID), mật khẩu và để robot gần router rồi thử lại.';
    case WIFI_EC.CONNECT_TIMEOUT:
      return 'Hết thời gian chờ robot vào Wi-Fi. Kiểm tra tên mạng có đúng và router đang phát sóng 2.4 GHz, rồi thử lại.';
    case WIFI_EC.NEED_WEB_LOGIN:
      return 'Wi-Fi này yêu cầu đăng nhập qua trang web nên robot không dùng được. Hãy chọn mạng khác.';
    case WIFI_EC.NO_INTERNET:
    case WIFI_EC.PING_ERROR:
      return 'Robot đã thử vào Wi-Fi nhưng không truy cập được Internet. Kiểm tra router hoặc chọn mạng khác.';
    case WIFI_EC.ALREADY_CONNECTED:
      return 'Robot báo đã kết nối sẵn với mạng này.';
    case WIFI_EC.OTHER_DEVICE:
      return 'Robot đang được thiết bị khác kết nối. Hãy đóng ứng dụng khác rồi thử lại.';
    case WIFI_EC.TVS_LOGIN_ERROR:
    case WIFI_EC.TVS_ERROR:
      return `Robot báo lỗi dịch vụ giọng nói (mã ${ec}).`;
    case WIFI_EC.ERROR_4G:
    case WIFI_EC.ERROR_4G_NO_SIM:
      return `Robot báo lỗi mạng di động (mã ${ec}).`;
    default:
      return `Robot báo lỗi Wi-Fi (mã ${ec ?? 'không rõ'}).`;
  }
}

export const MESSAGES = {
  handshakeTimeout: 'Robot không phản hồi bắt tay Bluetooth. Hãy tắt ứng dụng khác đang kết nối robot rồi thử lại.',
  handshakeRejected: (errorCode: number) =>
    errorCode === -1 || errorCode === -2
      ? `Robot đang được thiết bị khác giữ kết nối (mã ${errorCode}). Hãy ngắt thiết bị đó rồi thử lại.`
      : `Robot từ chối bắt tay Bluetooth (mã ${errorCode}).`,
  otherDeviceConfiguring: 'Robot đang được thiết bị khác cấu hình mạng. Hãy đợi hoặc khởi động lại robot.',
  wifiTimeout: 'Không nhận được kết quả Wi-Fi từ robot. Hãy kiểm tra robot đã nói "kết nối mạng thành công" chưa, rồi thử lại.',
  linkLost: 'Mất kết nối Bluetooth với robot. Hãy để điện thoại gần robot và thử lại.',
  linkLostAfterWifi:
    'Mất kết nối Bluetooth trước khi robot báo kết quả Wi-Fi. Robot có thể vẫn đang vào mạng — hãy kiểm tra trên server trước khi thử lại.',
} as const;
