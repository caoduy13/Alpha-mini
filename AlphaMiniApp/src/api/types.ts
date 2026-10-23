export type StatusResponse = {
  server?: string;
  robot_enabled?: boolean;
  robot_online?: boolean;
  robot_ip?: string;
  robot_type?: string;
  model?: string;
  robot_tts?: Record<string, unknown>;
  robot_last_connect_error?: string | null;
  [key: string]: unknown;
};

export type ChatResponse = {
  reply: string;
  robot_online: boolean;
  action_detected: boolean;
  robot_action_ok?: boolean | null;
  robot_action_error?: string | null;
  transcript?: string | null;
};

export type QrCodeItem = {
  text: string;
  format?: string;
};

export type RobotQrScanResponse = {
  ok: boolean;
  count?: number;
  codes?: QrCodeItem[];
  reply?: string;
  fed_to_chat?: boolean;
  duplicate?: boolean;
  qr_text?: string;
  stages?: string[];
  error?: string | null;
};

export type QrDecodeResponse = {
  ok: boolean;
  count?: number;
  codes?: QrCodeItem[];
  decoder?: { pyzbar?: boolean; cv2?: boolean };
  history_entry?: Record<string, unknown> | null;
  reply?: string;
};

export type QrHistoryResponse =
  | {
      ok: true;
      count: number;
      items: Array<{
        ts: string;
        source: string;
        text: string;
        format?: string;
        fed_to_chat?: boolean;
      }>;
    }
  | { ok: false; items: []; note?: string };

export type RobotCameraB64Response = {
  ok: boolean;
  image_b64: string;
  cached?: string;
  stale?: string;
  poll_sec?: number;
};
