import type { RouteProp } from '@react-navigation/native';
import { useFocusEffect } from '@react-navigation/native';
import React, { useCallback, useRef, useState } from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { ChatBubble } from '../components/ChatBubble';
import { VoiceRecordButton } from '../components/VoiceRecordButton';
import { useApp } from '../context/AppContext';
import { useChat } from '../hooks/useChat';
import { useSettings } from '../hooks/useSettings';
import type { TabParamList } from '../navigation/types';
import { colors, font, radius, spacing } from '../theme';

type Props = { route: RouteProp<TabParamList, 'Chat'> };

export function ChatScreen({ route }: Props) {
  const { setLastChat } = useApp();
  const { prefs } = useSettings();
  const listRef = useRef<FlatList>(null);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);

  const onExchange = useCallback(
    (user: string, bot: string) => setLastChat(user, bot),
    [setLastChat],
  );

  const { messages, sendMessage, sendVoice } = useChat(onExchange);

  const focusMic = route.params?.focusMic;

  useFocusEffect(
    useCallback(() => {
      if (focusMic) {
        setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 300);
      }
    }, [focusMic]),
  );

  async function onSendText() {
    if (!draft.trim() || sending) {
      return;
    }
    setSending(true);
    try {
      await sendMessage(draft, prefs.robotSpeakReplies);
      setDraft('');
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
    } finally {
      setSending(false);
    }
  }

  async function onVoice(uri: string) {
    setSending(true);
    try {
      await sendVoice(uri, prefs.robotSpeakReplies);
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
    } finally {
      setSending(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={72}>
        <View style={styles.header}>
          <MaterialCommunityIcons name="robot" size={22} color={colors.accent} />
          <Text style={styles.hTitle}>Alpha Mini</Text>
        </View>

        {focusMic ? (
          <View style={styles.banner}>
            <Text style={styles.bannerTxt}>
              Giữ nút mic để gửi giọng nói lên /voice/chat
            </Text>
          </View>
        ) : null}

        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.list}
          onContentSizeChange={() =>
            listRef.current?.scrollToEnd({ animated: true })
          }
          renderItem={({ item }) => (
            <ChatBubble
              role={item.role}
              text={item.text}
              timeLabel={new Date(item.ts).toLocaleTimeString('vi-VN', {
                hour: '2-digit',
                minute: '2-digit',
              })}
              badge={
                item.role === 'bot' && item.meta?.action_detected
                  ? 'Robot intent'
                  : undefined
              }
            />
          )}
        />

        <View style={styles.inputBar}>
          <VoiceRecordButton disabled={sending} onRecorded={onVoice} />
          <TextInput
            style={styles.input}
            placeholder="Nhắn tin…"
            placeholderTextColor={colors.textMuted}
            value={draft}
            onChangeText={setDraft}
            onSubmitEditing={onSendText}
          />
          <Pressable style={styles.send} onPress={onSendText} disabled={sending}>
            <MaterialCommunityIcons name="send" size={22} color={colors.text} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  hTitle: { color: colors.text, fontSize: font.title, fontWeight: '700' },
  banner: {
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    padding: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.successBg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  bannerTxt: { color: colors.success, fontSize: font.small },
  list: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
    gap: spacing.xs,
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    backgroundColor: colors.card,
  },
  input: {
    flex: 1,
    color: colors.text,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    fontSize: font.body,
  },
  send: {
    padding: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accentBg,
  },
});
