import { useCallback, useMemo, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { deleteQrHistory, getQrHistory } from '../api/endpoints';
import type { QrHistoryResponse } from '../api/types';

export type QrFilter = 'all' | 'robot' | 'camera' | 'upload';

export function useQRHistory() {
  const [data, setData] = useState<QrHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<QrFilter>('all');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getQrHistory(200);
      setData(res);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh]),
  );

  const items = useMemo(() => {
    if (!data || !data.ok || !('items' in data)) {
      return [];
    }
    const raw = data.items.slice().reverse();
    if (filter === 'all') {
      return raw;
    }
    if (filter === 'robot') {
      return raw.filter(i => i.source === 'robot');
    }
    if (filter === 'camera') {
      return raw.filter(i =>
        ['pc', 'phone', 'phone_ml'].includes(i.source.toLowerCase()),
      );
    }
    return raw.filter(i => i.source === 'upload');
  }, [data, filter]);

  const stats = useMemo(() => {
    if (!data || !data.ok || !('items' in data)) {
      return { total: 0, gemini: 0 };
    }
    const arr = data.items;
    return {
      total: arr.length,
      gemini: arr.filter(i => i.fed_to_chat).length,
    };
  }, [data]);

  const clearRemote = useCallback(async () => {
    await deleteQrHistory();
    await refresh();
  }, [refresh]);

  return {
    data,
    items,
    loading,
    filter,
    setFilter,
    stats,
    refresh,
    clearRemote,
  };
}
