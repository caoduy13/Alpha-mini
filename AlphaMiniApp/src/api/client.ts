import axios, { type AxiosError } from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

export const STORAGE_KEYS = {
  serverUrl: 'alphamini_server_url',
  skillToken: 'alphamini_skill_token',
  autoChatGemini: 'alphamini_auto_chat_gemini',
  robotSpeakReplies: 'alphamini_robot_speak_replies',
  onboardingDone: 'alphamini_onboarding_done',
  lastSSID: 'alphamini_last_ssid',
  lastConnectedAt: 'alphamini_last_connected_at',
  lastChainSummary: 'alphamini_last_chain_summary',
} as const;

const api = axios.create({
  timeout: 45000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use(async config => {
  const serverUrl = await AsyncStorage.getItem(STORAGE_KEYS.serverUrl);
  const token = await AsyncStorage.getItem(STORAGE_KEYS.skillToken);
  if (serverUrl) {
    config.baseURL = serverUrl.replace(/\/+$/, '');
  }
  if (token) {
    config.headers['X-Alphamini-Token'] = token;
  }
  // multipart: để axios set boundary
  if (
    typeof FormData !== 'undefined' &&
    config.data instanceof FormData &&
    config.headers
  ) {
    delete (config.headers as Record<string, unknown>)['Content-Type'];
  }
  return config;
});

export type ConnErrorKind =
  | 'cleartext'
  | 'cert'
  | 'refused'
  | 'timeout'
  | 'dns'
  | 'unauthorized'
  | 'server'
  | 'unknown';

export interface ConnError {
  kind: ConnErrorKind;
  message: string;
  detail: string;
  fixHint?: string;
}

export type Result<T, E> = { ok: true; data: T } | { ok: false; error: E };

function errorDetail(e: unknown): string {
  if (e instanceof Error && e.stack) {
    return `${e.message}\n${e.stack}`;
  }
  const ax = e as AxiosError;
  if (ax?.response?.data != null) {
    try {
      return `${String(ax.message)}\n${JSON.stringify(ax.response.data).slice(0, 2000)}`;
    } catch {
      /* ignore */
    }
  }
  return String((e as Error)?.message ?? e);
}

/** Classify fetch/axios/React Native network failures for user-facing hints. */
export function classifyError(e: any, response?: Response): ConnError {
  const ax = e as AxiosError | undefined;
  const httpStatus = response?.status ?? ax?.response?.status;
  const msg = String(e?.message ?? e?.code ?? e ?? '').toLowerCase();
  const code = String(e?.code ?? '').toLowerCase();
  const detail = errorDetail(e);

  if (httpStatus === 401 || httpStatus === 403) {
    return {
      kind: 'unauthorized',
      message: 'Token không đúng hoặc đã hết hạn',
      fixHint:
        'Kiểm tra X-Alphamini-Token, hoặc bỏ trống nếu server không yêu cầu auth.',
      detail,
    };
  }
  if (httpStatus != null && httpStatus >= 500) {
    return {
      kind: 'server',
      message: `Server lỗi (${httpStatus})`,
      fixHint:
        'Kiểm tra log server.py — có thể robot offline hoặc Gemini API down.',
      detail,
    };
  }
  if (msg.includes('cleartext') || msg.includes('not permitted')) {
    return {
      kind: 'cleartext',
      message: 'Android chặn HTTP plain text',
      fixHint:
        'Đã fix trong network_security_config.xml. Rebuild app: gradlew assembleDebug.',
      detail,
    };
  }
  if (
    msg.includes('certificate') ||
    msg.includes('ssl') ||
    msg.includes('trust') ||
    msg.includes('cert') ||
    code === 'err_ssl_pinning_failed'
  ) {
    return {
      kind: 'cert',
      message: 'SSL cert không hợp lệ',
      fixHint:
        'Cert tự ký? Tắt SSL trong server.py (dùng HTTP), hoặc cài cert vào device Settings → Security → Install certificates.',
      detail,
    };
  }
  if (
    code === 'econnrefused' ||
    msg.includes('econnrefused') ||
    msg.includes('connection refused')
  ) {
    return {
      kind: 'refused',
      message: 'Server không chạy hoặc sai port',
      fixHint:
        'Kiểm tra `python server.py` đang chạy trên PC. Đúng port? (mặc định 8000)',
      detail,
    };
  }
  if (
    code === 'etimedout' ||
    code === 'econnaborted' ||
    msg.includes('timeout') ||
    msg.includes('aborted')
  ) {
    return {
      kind: 'timeout',
      message: 'Kết nối timeout',
      fixHint:
        'Device và PC có cùng mạng WiFi không? Firewall PC có chặn port 8000?',
      detail,
    };
  }
  if (
    code === 'enotfound' ||
    msg.includes('enotfound') ||
    msg.includes('network request failed') ||
    msg.includes('network error') ||
    msg.includes('failed to connect')
  ) {
    return {
      kind: 'dns',
      message: 'Không tới được IP server',
      fixHint:
        'Kiểm tra IP đúng (chạy `ipconfig` trên PC để lấy IP LAN). Cùng WiFi với PC?',
      detail,
    };
  }
  return {
    kind: 'unknown',
    message: 'Lỗi không xác định',
    fixHint: 'Bấm "Copy log" và gửi cho dev.',
    detail,
  };
}

export async function tryApi<T>(
  fn: () => Promise<T>,
): Promise<Result<T, ConnError>> {
  try {
    const data = await fn();
    return { ok: true, data };
  } catch (e: unknown) {
    return { ok: false, error: classifyError(e as any) };
  }
}

export default api;
