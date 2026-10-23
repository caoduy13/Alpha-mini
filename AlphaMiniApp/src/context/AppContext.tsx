import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from 'react';
import { STORAGE_KEYS } from '../api/client';
import { IDLE_CHAIN, runConnectionChain, type ChainResult } from '../connection/chain';

export type AppState = {
  robotOnline: boolean;
  robotIp: string;
  robotType: string;
  lastUser: string;
  lastBot: string;
};

export type AppAction =
  | {
      type: 'robot/status';
      payload: { online: boolean; ip: string; robotType: string };
    }
  | { type: 'chat/last'; payload: { user: string; bot: string } };

const initialState: AppState = {
  robotOnline: false,
  robotIp: '',
  robotType: '',
  lastUser: '',
  lastBot: '',
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'robot/status':
      return {
        ...state,
        robotOnline: action.payload.online,
        robotIp: action.payload.ip,
        robotType: action.payload.robotType,
      };
    case 'chat/last':
      return {
        ...state,
        lastUser: action.payload.user,
        lastBot: action.payload.bot,
      };
    default:
      return state;
  }
}

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

type AppCtx = {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
  setLastChat: (user: string, bot: string) => void;
  onboardingHydrated: boolean;
  onboardingDone: boolean;
  setOnboardingDone: (v: boolean) => Promise<void>;
  lastSSID: string;
  setLastSSID: (v: string) => Promise<void>;
  connection: ChainResult;
  connect: () => Promise<void>;
  cancelConnect: () => void;
  disconnect: () => void;
  refreshConnection: () => Promise<boolean>;
};

const AppContext = createContext<AppCtx | undefined>(undefined);

const FIVE_MIN_MS = 5 * 60_000;

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const [onboardingHydrated, setHydrated] = useState(false);
  const [onboardingDone, setOnboardingDoneState] = useState(false);
  const [lastSSID, setLastSSIDState] = useState('');
  const [connection, setConnection] = useState<ChainResult>(IDLE_CHAIN);

  const abortRef = useRef<AbortController | null>(null);
  const connectionRef = useRef(connection);

  useEffect(() => {
    connectionRef.current = connection;
  }, [connection]);

  useEffect(() => {
    (async () => {
      const map = await AsyncStorage.getMany([
        STORAGE_KEYS.onboardingDone,
        STORAGE_KEYS.lastSSID,
      ]);
      setOnboardingDoneState(map[STORAGE_KEYS.onboardingDone] === 'true');
      setLastSSIDState(map[STORAGE_KEYS.lastSSID] ?? '');
      setHydrated(true);
    })();
  }, []);

  const setOnboardingDone = useCallback(async (v: boolean) => {
    await AsyncStorage.setItem(
      STORAGE_KEYS.onboardingDone,
      v ? 'true' : 'false',
    );
    setOnboardingDoneState(v);
  }, []);

  const setLastSSID = useCallback(async (v: string) => {
    const t = v.trim();
    await AsyncStorage.setItem(STORAGE_KEYS.lastSSID, t);
    setLastSSIDState(t);
  }, []);

  const setLastChat = useCallback((user: string, bot: string) => {
    dispatch({ type: 'chat/last', payload: { user, bot } });
  }, []);

  const refreshConnectionInner = useCallback(async (): Promise<boolean> => {
    const prev = connectionRef.current;
    if (prev.status === 'running') {
      return false;
    }
    const rawUrl = await AsyncStorage.getItem(STORAGE_KEYS.serverUrl);
    const token = await AsyncStorage.getItem(STORAGE_KEYS.skillToken);
    const base = normalizeBaseUrl(rawUrl ?? '');
    if (!base) {
      if (prev.status !== 'success') {
        setConnection(IDLE_CHAIN);
      }
      return false;
    }
    const headers: Record<string, string> = {};
    if (token?.trim()) {
      headers['X-Alphamini-Token'] = token.trim();
    }
    const tryDiagnose = async () => {
      const res = await axios.get(`${base}/connect/diagnose`, {
        timeout: 8000,
        headers,
        validateStatus: s => s === 200 || s === 404,
      });
      if (res.status !== 200) {
        throw new Error(`diagnose ${res.status}`);
      }
      return res.data as {
        server?: { version?: string };
        robot?: {
          ip?: string | null;
          online?: boolean;
          registered?: boolean;
          battery?: number | null;
          mood?: string | null;
          robot_type?: string | null;
        };
      };
    };
    try {
      let data: Awaited<ReturnType<typeof tryDiagnose>>;
      try {
        data = await tryDiagnose();
      } catch {
        const st = await axios.get(`${base}/status`, {
          timeout: 8000,
          headers,
          validateStatus: s => s === 200,
        });
        if (st.status !== 200) {
          throw new Error('status fail');
        }
        const b = st.data as {
          robot_online?: boolean;
          robot_ip?: string;
          robot_type?: string;
          model?: string;
        };
        data = {
          server: { version: String(b.model ?? '') },
          robot: {
            registered: !!b.robot_online,
            online: !!b.robot_online,
            ip: b.robot_ip ? String(b.robot_ip) : null,
            battery: null,
            mood: null,
            robot_type: b.robot_type ? String(b.robot_type) : '',
          },
        };
      }
      const robotIp = (data.robot?.ip ?? '').trim();
      const robotType = String(data.robot?.robot_type ?? '');
      const summary: NonNullable<ChainResult['summary']> = {
        serverIp: hostFromUrl(base),
        serverVersion: String(data.server?.version ?? ''),
        robotIp: robotIp || undefined,
        robotType: robotType || undefined,
        battery:
          data.robot?.battery != null ? Number(data.robot.battery) : undefined,
        mood: data.robot?.mood != null ? String(data.robot.mood) : undefined,
      };
      setConnection({
        status: 'success',
        steps: [],
        summary,
        finishedAt: Date.now(),
      });
      dispatch({
        type: 'robot/status',
        payload: {
          online: !!data.robot?.online,
          ip: robotIp,
          robotType,
        },
      });
      return true;
    } catch {
      if (prev.status !== 'success') {
        setConnection(IDLE_CHAIN);
        dispatch({
          type: 'robot/status',
          payload: { online: false, ip: '', robotType: '' },
        });
      }
      return false;
    }
  }, []);

  /** Nền: gần đây đã thành công → làm mới trạng thái 1 request, không chạy animation chain. */
  useEffect(() => {
    if (!onboardingHydrated) {
      return;
    }
    let alive = true;
    (async () => {
      const map = await AsyncStorage.getMany([
        STORAGE_KEYS.lastConnectedAt,
        STORAGE_KEYS.serverUrl,
      ]);
      const lastAt = map[STORAGE_KEYS.lastConnectedAt];
      const url = map[STORAGE_KEYS.serverUrl];
      if (!alive || !url?.trim() || !lastAt) {
        return;
      }
      const t = Number(lastAt);
      if (!Number.isFinite(t) || Date.now() - t >= FIVE_MIN_MS) {
        return;
      }
      await refreshConnectionInner();
    })();
    return () => {
      alive = false;
    };
  }, [onboardingHydrated, refreshConnectionInner]);

  const refreshConnection = useCallback(async () => {
    return refreshConnectionInner();
  }, [refreshConnectionInner]);

  const cancelConnect = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setConnection(c =>
      c.status === 'running' ? IDLE_CHAIN : c,
    );
  }, []);

  const disconnect = useCallback(async () => {
    cancelConnect();
    await AsyncStorage.removeItem(STORAGE_KEYS.lastConnectedAt);
    await AsyncStorage.removeItem(STORAGE_KEYS.lastChainSummary);
    setConnection(IDLE_CHAIN);
    dispatch({
      type: 'robot/status',
      payload: { online: false, ip: '', robotType: '' },
    });
  }, [cancelConnect]);

  const connect = useCallback(async () => {
    cancelConnect();
    const ac = new AbortController();
    abortRef.current = ac;
    const rawUrl = await AsyncStorage.getItem(STORAGE_KEYS.serverUrl);
    const token = await AsyncStorage.getItem(STORAGE_KEYS.skillToken);
    const result = await runConnectionChain(
      {
        serverUrl: rawUrl ?? '',
        token: token ?? undefined,
        signal: ac.signal,
      },
      setConnection,
    );
    abortRef.current = null;
    if (result.status === 'success' && result.summary) {
      await AsyncStorage.setMany({
        [STORAGE_KEYS.lastConnectedAt]: String(Date.now()),
        [STORAGE_KEYS.lastChainSummary]: JSON.stringify(result.summary),
      });
      dispatch({
        type: 'robot/status',
        payload: {
          online: true,
          ip: String(result.summary.robotIp ?? ''),
          robotType: String(result.summary.robotType ?? ''),
        },
      });
    } else if (result.status === 'failed') {
      dispatch({
        type: 'robot/status',
        payload: { online: false, ip: '', robotType: '' },
      });
    }
  }, [cancelConnect]);

  const value = useMemo(
    () => ({
      state,
      dispatch,
      setLastChat,
      onboardingHydrated,
      onboardingDone,
      setOnboardingDone,
      lastSSID,
      setLastSSID,
      connection,
      connect,
      cancelConnect,
      disconnect,
      refreshConnection,
    }),
    [
      state,
      dispatch,
      setLastChat,
      onboardingHydrated,
      onboardingDone,
      setOnboardingDone,
      lastSSID,
      setLastSSID,
      connection,
      connect,
      cancelConnect,
      disconnect,
      refreshConnection,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error('useApp must be used within AppProvider');
  }
  return ctx;
}
