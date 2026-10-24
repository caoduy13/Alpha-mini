import { bleDiag } from '../ble/diagnostics';
import axios, { type AxiosError } from 'axios';
import { classifyError, type ConnError } from '../api/client';

export type StepStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped';

export type StepId =
  | 'validate'
  | 'reachServer'
  | 'robotRegistered'
  | 'connectRobot'
  | 'robotState';

export interface ChainStep {
  id: StepId;
  label: string;
  status: StepStatus;
  detail?: string;
  endpoint?: string;
  error?: ConnError;
  startedAt?: number;
  durationMs?: number;
}

export interface ChainResult {
  status: 'idle' | 'running' | 'success' | 'failed';
  steps: ChainStep[];
  failedStepId?: StepId;
  summary?: {
    serverIp: string;
    serverVersion: string;
    robotIp?: string;
    robotType?: string;
    battery?: number;
    mood?: string;
  };
  startedAt?: number;
  finishedAt?: number;
}

export interface ChainConfig {
  serverUrl: string;
  token?: string;
  signal?: AbortSignal;
}

export const IDLE_CHAIN: ChainResult = {
  status: 'idle',
  steps: [],
};

function normalizeBaseUrl(raw: string): string {
  const t = raw.trim().replace(/\/+$/, '');
  if (!t) {
    return '';
  }
  return /^https?:\/\//i.test(t) ? t : `http://${t}`;
}

function hostFromUrl(base: string): string {
  try {
    return new URL(base).host;
  } catch {
    return base;
  }
}

function cancelledError(): ConnError {
  return {
    kind: 'unknown',
    message: 'Đã hủy',
    fixHint: 'Bấm «Kết nối» khi sẵn sàng thử lại.',
    detail: 'Aborted',
  };
}

function assertNotAborted(signal: AbortSignal | undefined) {
  if (signal?.aborted) {
    throw Object.assign(new Error('aborted'), { code: 'ABORTED' });
  }
}

function axiosConnError(e: unknown, endpoint: string): ConnError {
  const ax = e as AxiosError;
  if ((e as { code?: string })?.code === 'ABORTED' || ax.code === 'ERR_CANCELED') {
    return cancelledError();
  }
  const c = classifyError(e);
  return {
    ...c,
    detail: `${endpoint}\n${c.detail}`,
  };
}

function templateSteps(): ChainStep[] {
  return [
    { id: 'validate', label: 'Kiểm tra cấu hình', status: 'pending' },
    { id: 'reachServer', label: 'Kết nối server', status: 'pending' },
    { id: 'robotRegistered', label: 'Server đã biết robot', status: 'pending' },
    { id: 'connectRobot', label: 'Kết nối robot', status: 'pending' },
    { id: 'robotState', label: 'Robot phản hồi', status: 'pending' },
  ];
}

type RobotStateBody = {
  registered?: boolean;
  online?: boolean;
  ip?: string | null;
  battery?: number | null;
  mood?: string | null;
  robot_type?: string | null;
};

export async function runConnectionChain(
  config: ChainConfig,
  onUpdate: (result: ChainResult) => void,
): Promise<ChainResult> {
  const steps = templateSteps();
  const result: ChainResult = {
    status: 'running',
    steps,
    startedAt: Date.now(),
  };
  const summary: NonNullable<ChainResult['summary']> = {
    serverIp: '',
    serverVersion: '',
  };
  result.summary = summary;
  onUpdate({ ...result, steps: [...steps] });

  const signal = config.signal;
  const baseURL = normalizeBaseUrl(config.serverUrl);
  bleDiag('lan-chain-start', {serverUrl: baseURL, authHeaderPresent: Boolean(config.token)});
  const headers: Record<string, string> = {};
  if (config.token?.trim()) {
    headers['X-Alphamini-Token'] = config.token.trim();
  }

  const setStep = (id: StepId, patch: Partial<ChainStep>) => {
    const s = steps.find(x => x.id === id)!;
    Object.assign(s, patch);
    bleDiag('lan-step', {id, status: s.status, endpoint: s.endpoint, durationMs: s.durationMs, error: s.error});
    if (patch.status === 'failed') {
      result.status = 'failed';
      result.failedStepId = id;
      result.finishedAt = Date.now();
    }
    onUpdate({ ...result, steps: [...steps] });
  };

  const markAllPendingAfter = (afterId: StepId, status: StepStatus = 'pending') => {
    let seen = false;
    for (const st of steps) {
      if (st.id === afterId) {
        seen = true;
        continue;
      }
      if (seen && st.status === 'pending') {
        st.status = status;
      }
    }
  };

  try {
    // Step 1: validate
    assertNotAborted(signal);
    const tValidate = Date.now();
    setStep('validate', { status: 'running', startedAt: tValidate });
    if (!baseURL) {
      setStep('validate', {
        status: 'failed',
        endpoint: '(local)',
        error: {
          kind: 'unknown',
          message: 'Chưa có địa chỉ server',
          fixHint:
            'Mở Cài đặt, nhập IP máy PC (vd. 192.168.1.5) và port 8000, rồi Lưu.',
          detail: 'serverUrl empty',
        },
        durationMs: Date.now() - tValidate,
      });
      markAllPendingAfter('validate', 'skipped');
      onUpdate({ ...result, steps: [...steps] });
      return result;
    }
    try {
      // eslint-disable-next-line no-new
      new URL(baseURL);
    } catch {
      setStep('validate', {
        status: 'failed',
        endpoint: '(local)',
        error: {
          kind: 'unknown',
          message: 'URL server không hợp lệ',
          fixHint: 'Dùng dạng http://IP:8000 hoặc https://IP:8443',
          detail: config.serverUrl,
        },
        durationMs: Date.now() - tValidate,
      });
      markAllPendingAfter('validate', 'skipped');
      onUpdate({ ...result, steps: [...steps] });
      return result;
    }
    setStep('validate', {
      status: 'success',
      detail: 'OK',
      endpoint: '(local)',
      durationMs: Date.now() - tValidate,
    });
    onUpdate({ ...result, steps: [...steps] });

    // Step 2: GET /status
    assertNotAborted(signal);
    const epStatus = `${baseURL}/status`;
    const t2 = Date.now();
    setStep('reachServer', { status: 'running', startedAt: t2, endpoint: epStatus });
    onUpdate({ ...result, steps: [...steps] });

    let statusBody: Record<string, unknown>;
    try {
      const res = await axios.get(epStatus, {
        timeout: 5000,
        signal,
        headers,
        validateStatus: () => true,
      });
      if (res.status === 401 || res.status === 403) {
        throw Object.assign(new Error('unauthorized'), {
          response: { status: res.status, data: res.data },
        });
      }
      if (res.status >= 500) {
        throw Object.assign(new Error(`server ${res.status}`), {
          response: { status: res.status, data: res.data },
        });
      }
      if (res.status !== 200) {
        throw new Error(`HTTP ${res.status}`);
      }
      statusBody = res.data as Record<string, unknown>;
    } catch (e) {
      const err = axiosConnError(e, epStatus);
      if (err.kind === 'dns' || err.kind === 'timeout') {
        err.fixHint = `${err.fixHint ?? ''} Cùng WiFi với PC chạy server?`.trim();
      }
      if (err.kind === 'refused') {
        err.message = 'Server không chạy hoặc sai port';
      }
      setStep('reachServer', {
        status: 'failed',
        error: err,
        endpoint: epStatus,
        durationMs: Date.now() - t2,
      });
      markAllPendingAfter('reachServer', 'skipped');
      onUpdate({ ...result, steps: [...steps] });
      return result;
    }

    const ms2 = Date.now() - t2;
    summary.serverIp = hostFromUrl(baseURL);
    summary.serverVersion = String(statusBody.model ?? statusBody.server ?? 'OK');
    summary.robotType = String(statusBody.robot_type ?? '');
    setStep('reachServer', {
      status: 'success',
      detail: `${summary.serverIp} · ${ms2}ms`,
      endpoint: epStatus,
      durationMs: ms2,
    });
    onUpdate({ ...result, steps: [...steps] });

    // Step 3: GET /robot/state
    assertNotAborted(signal);
    const epState = `${baseURL}/robot/state`;
    const t3 = Date.now();
    setStep('robotRegistered', {
      status: 'running',
      startedAt: t3,
      endpoint: epState,
    });
    onUpdate({ ...result, steps: [...steps] });

    let state1: RobotStateBody;
    try {
      const res = await axios.get(epState, {
        timeout: 8000,
        signal,
        headers,
        validateStatus: () => true,
      });
      if (res.status >= 500) {
        throw Object.assign(new Error(`server ${res.status}`), {
          response: { status: res.status },
        });
      }
      if (res.status !== 200) {
        throw new Error(`HTTP ${res.status}`);
      }
      state1 = res.data as RobotStateBody;
    } catch (e) {
      const err = axiosConnError(e, epState);
      err.message =
        err.kind === 'server'
          ? 'Server lỗi nội bộ'
          : 'Không đọc được trạng thái robot';
      setStep('robotRegistered', {
        status: 'failed',
        error: err,
        endpoint: epState,
        durationMs: Date.now() - t3,
      });
      markAllPendingAfter('robotRegistered', 'skipped');
      onUpdate({ ...result, steps: [...steps] });
      return result;
    }

    const registered = !!state1.registered || !!state1.online;
    const robotIpKnown = (state1.ip ?? '').trim();
    setStep('robotRegistered', {
      status: 'success',
      detail: registered
        ? `Robot ${robotIpKnown || 'đã kết nối'}`
        : 'Chưa có phiên SDK — cần kết nối',
      endpoint: epState,
      durationMs: Date.now() - t3,
    });
    onUpdate({ ...result, steps: [...steps] });

    // Step 4: POST /robot/connect (skip if already registered)
    assertNotAborted(signal);
    const epConnect = `${baseURL}/robot/connect`;
    if (registered) {
      setStep('connectRobot', {
        status: 'skipped',
        detail: 'Đã kết nối từ trước',
        endpoint: epConnect,
      });
      summary.robotIp = robotIpKnown || summary.robotIp;
    } else {
      const t4 = Date.now();
      setStep('connectRobot', {
        status: 'running',
        startedAt: t4,
        endpoint: epConnect,
      });
      onUpdate({ ...result, steps: [...steps] });

      try {
        const res = await axios.post(
          epConnect,
          {},
          { timeout: 15000, signal, headers, validateStatus: () => true },
        );
        if (res.status === 404) {
          const detail =
            (res.data as { detail?: string })?.detail ?? 'Không quét thấy robot';
          setStep('connectRobot', {
            status: 'failed',
            endpoint: epConnect,
            error: {
              kind: 'unknown',
              message: 'Robot offline hoặc không thấy trên mạng',
              fixHint:
                'Bật robot và đảm bảo cùng WiFi với PC chạy server. Thử «Quét lại».',
              detail: String(detail),
            },
            durationMs: Date.now() - t4,
          });
          markAllPendingAfter('connectRobot', 'skipped');
          onUpdate({ ...result, steps: [...steps] });
          return result;
        }
        if (res.status === 401 || res.status === 403) {
          throw Object.assign(new Error('unauthorized'), {
            response: { status: res.status },
          });
        }
        if (res.status >= 500) {
          throw Object.assign(new Error(`server ${res.status}`), {
            response: { status: res.status, data: res.data },
          });
        }
        if (res.status !== 200) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = res.data as { robot_ip?: string; connected?: boolean };
        const rip = String(data.robot_ip ?? '').trim();
        summary.robotIp = rip || summary.robotIp;
        setStep('connectRobot', {
          status: 'success',
          detail: rip ? `Đã kết nối ${rip}` : 'Đã kết nối',
          endpoint: epConnect,
          durationMs: Date.now() - t4,
        });
      } catch (e) {
        const err = axiosConnError(e, epConnect);
        if (err.message === 'Đã hủy') {
          setStep('connectRobot', {
            status: 'failed',
            error: err,
            endpoint: epConnect,
            durationMs: Date.now() - t4,
          });
        } else {
          setStep('connectRobot', {
            status: 'failed',
            error: {
              ...err,
              message:
                err.kind === 'timeout'
                  ? 'Kết nối robot quá lâu (timeout)'
                  : err.message,
            },
            endpoint: epConnect,
            durationMs: Date.now() - t4,
          });
        }
        markAllPendingAfter('connectRobot', 'skipped');
        onUpdate({ ...result, steps: [...steps] });
        return result;
      }
      onUpdate({ ...result, steps: [...steps] });
    }

    // Step 5: GET /robot/state again
    assertNotAborted(signal);
    const t5 = Date.now();
    setStep('robotState', {
      status: 'running',
      startedAt: t5,
      endpoint: epState,
    });
    onUpdate({ ...result, steps: [...steps] });

    let state2: RobotStateBody;
    try {
      const res = await axios.get(epState, {
        timeout: 8000,
        signal,
        headers,
        validateStatus: () => true,
      });
      if (res.status !== 200) {
        throw new Error(`HTTP ${res.status}`);
      }
      state2 = res.data as RobotStateBody;
    } catch (e) {
      const err = axiosConnError(e, epState);
      setStep('robotState', {
        status: 'failed',
        error: {
          ...err,
          message: 'Kết nối robot không ổn định',
          fixHint: 'Thử «Reconnect» trên server hoặc khởi động lại robot.',
        },
        endpoint: epState,
        durationMs: Date.now() - t5,
      });
      markAllPendingAfter('robotState', 'skipped');
      onUpdate({ ...result, steps: [...steps] });
      return result;
    }

    if (!state2.online && !state2.registered) {
      setStep('robotState', {
        status: 'failed',
        endpoint: epState,
        error: {
          kind: 'unknown',
          message: 'Robot không phản hồi sau khi kết nối',
          fixHint: 'Thử «Reconnect» hoặc tắt/bật robot.',
          detail: JSON.stringify(state2),
        },
        durationMs: Date.now() - t5,
      });
      result.status = 'failed';
      result.failedStepId = 'robotState';
      result.finishedAt = Date.now();
      onUpdate({ ...result, steps: [...steps] });
      return result;
    }

    summary.robotIp = (state2.ip ?? summary.robotIp ?? '').trim() || summary.robotIp;
    if (!summary.robotType && statusBody.robot_type) {
      summary.robotType = String(statusBody.robot_type);
    }
    if (!summary.robotType && state2.robot_type) {
      summary.robotType = String(state2.robot_type);
    }
    summary.battery =
      state2.battery != null && state2.battery !== undefined
        ? Number(state2.battery)
        : undefined;
    summary.mood = state2.mood != null ? String(state2.mood) : undefined;

    const pin =
      summary.battery != null && !Number.isNaN(summary.battery)
        ? `${summary.battery}%`
        : null;
    const moodStr = summary.mood ? ` · ${summary.mood}` : '';
    setStep('robotState', {
      status: 'success',
      detail: `${summary.robotIp || 'robot'}${pin ? ` · pin ${pin}` : ''}${moodStr}`,
      endpoint: epState,
      durationMs: Date.now() - t5,
    });

    result.status = 'success';
    result.failedStepId = undefined;
    result.finishedAt = Date.now();
    onUpdate({ ...result, steps: [...steps] });
    return result;
  } catch (e) {
    const ax = e as AxiosError;
    const aborted =
      signal?.aborted ||
      ax.code === 'ERR_CANCELED' ||
      (e as { code?: string })?.code === 'ABORTED';
    result.finishedAt = Date.now();
    const running = steps.find(s => s.status === 'running');
    if (aborted && running) {
      result.status = 'failed';
      result.failedStepId = running.id;
      setStep(running.id, {
        status: 'failed',
        error: cancelledError(),
        durationMs: running.startedAt ? Date.now() - running.startedAt : undefined,
      });
      markAllPendingAfter(running.id, 'skipped');
    } else if (running) {
      result.status = 'failed';
      result.failedStepId = running.id;
      setStep(running.id, {
        status: 'failed',
        error: axiosConnError(e, running.endpoint ?? '(unknown)'),
        durationMs: running.startedAt ? Date.now() - running.startedAt : undefined,
      });
      markAllPendingAfter(running.id, 'skipped');
    }
    onUpdate({ ...result, steps: [...steps] });
    return result;
  }
}
