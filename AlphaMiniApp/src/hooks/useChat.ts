import { useCallback, useState } from 'react';
import { postChat, postVoiceChat } from '../api/endpoints';
import type { ChatResponse } from '../api/types';

export type ChatMsg = {
  id: string;
  role: 'user' | 'bot';
  text: string;
  ts: number;
  transcript?: string;
  meta?: Partial<ChatResponse>;
};

export function useChat(onExchange?: (user: string, bot: string) => void) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);

  const appendBotWithMeta = useCallback(
    (userLine: string, res: ChatResponse) => {
      setMessages(prev => [
        ...prev,
        {
          id: `${Date.now()}-b`,
          role: 'bot',
          text: res.reply,
          ts: Date.now(),
          transcript: res.transcript ?? undefined,
          meta: res,
        },
      ]);
      onExchange?.(userLine, res.reply);
    },
    [onExchange],
  );

  const sendMessage = useCallback(
    async (text: string, speak: boolean) => {
      const trimmed = text.trim();
      if (!trimmed) {
        return;
      }
      const uid = `${Date.now()}-u`;
      setMessages(prev => [
        ...prev,
        { id: uid, role: 'user', text: trimmed, ts: Date.now() },
      ]);
      const res = await postChat(trimmed, speak);
      appendBotWithMeta(trimmed, res);
    },
    [appendBotWithMeta],
  );

  const sendVoice = useCallback(
    async (fileUri: string, speak: boolean) => {
      const uid = `${Date.now()}-v`;
      setMessages(prev => [
        ...prev,
        { id: uid, role: 'user', text: '🎤 …', ts: Date.now() },
      ]);
      const res = await postVoiceChat(fileUri, speak);
      setMessages(prev =>
        prev.map(m =>
          m.id === uid
            ? {
                ...m,
                text: res.transcript?.trim()
                  ? `[Giọng nói] ${res.transcript}`
                  : '[Giọng nói]',
                transcript: res.transcript ?? undefined,
              }
            : m,
        ),
      );
      appendBotWithMeta(res.transcript || '[voice]', res);
    },
    [appendBotWithMeta],
  );

  const clear = useCallback(() => setMessages([]), []);

  return { messages, sendMessage, sendVoice, clear };
}
