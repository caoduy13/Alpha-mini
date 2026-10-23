import api from './client';
import type {
  ChatResponse,
  QrDecodeResponse,
  QrHistoryResponse,
  RobotCameraB64Response,
  RobotQrScanResponse,
  StatusResponse,
} from './types';

export async function getStatus(): Promise<StatusResponse> {
  const { data } = await api.get<StatusResponse>('/status');
  return data;
}

export async function postChat(text: string, speak: boolean): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>('/chat', { text, speak });
  return data;
}

export async function postVoiceChat(uri: string, speak: boolean): Promise<ChatResponse> {
  const form = new FormData();
  form.append('audio', {
    uri,
    type: 'audio/m4a',
    name: 'voice.m4a',
  } as never);
  form.append('speak', speak ? 'true' : 'false');
  const { data } = await api.post<ChatResponse>('/voice/chat', form);
  return data;
}

export async function robotTrigger(
  cmd: string,
  extra?: Record<string, string>,
): Promise<{ ok: boolean; action?: string; [k: string]: unknown }> {
  const q = new URLSearchParams({ cmd, ...(extra || {}) });
  const { data } = await api.get(`/robot/trigger?${q.toString()}`);
  return data;
}

export async function getRobotCameraFrameB64(): Promise<RobotCameraB64Response> {
  const { data } = await api.get<RobotCameraB64Response>('/robot/camera/frame', {
    params: { b64: true },
  });
  return data;
}

export async function postRobotConnect(): Promise<unknown> {
  const { data } = await api.post('/robot/connect');
  return data;
}

export async function postRobotReconnect(): Promise<unknown> {
  const { data } = await api.post('/robot/reconnect');
  return data;
}

export async function postRobotQrFromCamera(
  autoChat?: boolean,
): Promise<RobotQrScanResponse> {
  const params =
    autoChat === undefined ? {} : { auto_chat: autoChat ? 'true' : 'false' };
  const { data } = await api.post<RobotQrScanResponse>(
    '/robot/qr/from_camera',
    undefined,
    { params },
  );
  return data;
}

export async function postQrDecodeFile(uri: string): Promise<QrDecodeResponse> {
  const form = new FormData();
  form.append('file', {
    uri,
    type: 'image/jpeg',
    name: 'qr.jpg',
  } as never);
  const { data } = await api.post<QrDecodeResponse>('/qr/decode', form);
  return data;
}

export async function postQrDecodeBase64(
  imageB64: string,
  source = 'phone',
): Promise<QrDecodeResponse> {
  const { data } = await api.post<QrDecodeResponse>('/qr/decode_base64', {
    image_b64: imageB64,
    source,
  });
  return data;
}

export async function getQrHistory(limit = 50): Promise<QrHistoryResponse> {
  const { data } = await api.get<QrHistoryResponse>('/qr/history', {
    params: { limit },
  });
  return data;
}

export async function deleteQrHistory(): Promise<{ ok: boolean; cleared: number }> {
  const { data } = await api.delete<{ ok: boolean; cleared: number }>(
    '/qr/history',
  );
  return data;
}

export async function getRobotDiagnose(): Promise<unknown> {
  const { data } = await api.get('/robot/diagnose');
  return data;
}

export async function getRobotScan(): Promise<unknown> {
  const { data } = await api.get('/robot/scan');
  return data;
}
