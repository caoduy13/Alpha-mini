import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import { STORAGE_KEYS } from '../api/client';

export type SettingsPrefs = {
  serverUrl: string;
  skillToken: string;
  autoChatGemini: boolean;
  robotSpeakReplies: boolean;
};

const defaults: SettingsPrefs = {
  serverUrl: '',
  skillToken: '',
  autoChatGemini: true,
  robotSpeakReplies: true,
};

export function useSettings() {
  const [prefs, setPrefs] = useState<SettingsPrefs>(defaults);

  const load = useCallback(async () => {
    const keys = [
      STORAGE_KEYS.serverUrl,
      STORAGE_KEYS.skillToken,
      STORAGE_KEYS.autoChatGemini,
      STORAGE_KEYS.robotSpeakReplies,
    ] as const;
    const map = await AsyncStorage.getMany([...keys]);
    setPrefs({
      serverUrl: map[STORAGE_KEYS.serverUrl] ?? '',
      skillToken: map[STORAGE_KEYS.skillToken] ?? '',
      autoChatGemini: map[STORAGE_KEYS.autoChatGemini] !== 'false',
      robotSpeakReplies: map[STORAGE_KEYS.robotSpeakReplies] !== 'false',
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const persist = useCallback(async (patch: Partial<SettingsPrefs>) => {
    const keys = [
      STORAGE_KEYS.serverUrl,
      STORAGE_KEYS.skillToken,
      STORAGE_KEYS.autoChatGemini,
      STORAGE_KEYS.robotSpeakReplies,
    ] as const;
    const map = await AsyncStorage.getMany([...keys]);
    const prev: SettingsPrefs = {
      serverUrl: map[STORAGE_KEYS.serverUrl] ?? '',
      skillToken: map[STORAGE_KEYS.skillToken] ?? '',
      autoChatGemini: map[STORAGE_KEYS.autoChatGemini] !== 'false',
      robotSpeakReplies: map[STORAGE_KEYS.robotSpeakReplies] !== 'false',
    };
    const merged = { ...prev, ...patch };
    await AsyncStorage.setMany({
      [STORAGE_KEYS.serverUrl]: merged.serverUrl.trim(),
      [STORAGE_KEYS.skillToken]: merged.skillToken.trim(),
      [STORAGE_KEYS.autoChatGemini]: merged.autoChatGemini ? 'true' : 'false',
      [STORAGE_KEYS.robotSpeakReplies]: merged.robotSpeakReplies
        ? 'true'
        : 'false',
    });
    setPrefs(merged);
  }, []);

  return { prefs, reload: load, persist };
}
