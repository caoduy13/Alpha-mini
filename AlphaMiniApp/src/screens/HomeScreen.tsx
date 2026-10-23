import type { CompositeNavigationProp } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import React, { useCallback, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { postChat, robotTrigger } from '../api/endpoints';
import { CameraPreview } from '../components/CameraPreview';
import { ConnectionPanel } from '../components/ConnectionPanel';
import { ControlPanel } from '../components/ControlPanel';
import { QuickActionGrid } from '../components/QuickActionGrid';
import { RobotStatusBadge } from '../components/RobotStatusBadge';
import { useApp } from '../context/AppContext';
import { useSettings } from '../hooks/useSettings';
import type { RootStackParamList, TabParamList } from '../navigation/types';
import { colors, font, radius, spacing } from '../theme';
import { truncate } from '../utils/format';

type Nav = CompositeNavigationProp<
  BottomTabNavigationProp<TabParamList, 'Home'>,
  NativeStackNavigationProp<RootStackParamList>
>;

export function HomeScreen() {
  const navigation = useNavigation<Nav>();
  const { state, setLastChat } = useApp();
  const { prefs } = useSettings();
  const [draft, setDraft] = useState('');
  const [ctrl, setCtrl] = useState(false);

  const sendQuick = useCallback(async () => {
    const t = draft.trim();
    if (!t) {
      return;
    }
    try {
      const res = await postChat(t, prefs.robotSpeakReplies);
      setLastChat(t, res.reply);
      setDraft('');
    } catch {
      setLastChat(t, 'Lỗi kết nối server.');
    }
  }, [draft, prefs.robotSpeakReplies, setLastChat]);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          stickyHeaderIndices={[0]}
          contentContainerStyle={styles.scroll}>
          <View style={styles.stickyConn}>
            <ConnectionPanel autoRun />
          </View>
          <View style={styles.header}>
            <View style={styles.avatar}>
              <MaterialCommunityIcons name="robot" size={26} color={colors.accent} />
            </View>
            <View style={styles.headerMid}>
              <Text style={styles.title}>Alpha Mini</Text>
              <RobotStatusBadge online={state.robotOnline} />
            </View>
            <Pressable
              onPress={() => navigation.navigate('Settings')}
              hitSlop={12}
              style={styles.iconBtn}>
              <MaterialCommunityIcons name="cog" size={26} color={colors.text} />
            </Pressable>
          </View>

          <CameraPreview robotOnline={state.robotOnline} />

          <QuickActionGrid
            actions={[
              {
                key: 'qr',
                label: 'Scan QR',
                sub: 'Camera robot / điện thoại',
                icon: 'qrcode',
                bg: colors.accentBg,
                onPress: () => navigation.navigate('QRScan'),
              },
              {
                key: 'voice',
                label: 'Voice chat',
                sub: 'Giữ mic ở tab Chat',
                icon: 'microphone',
                bg: colors.successBg,
                onPress: () =>
                  navigation.navigate('Chat', { focusMic: true }),
              },
              {
                key: 'dance',
                label: 'Dance',
                sub: 'Nhảy mặc định',
                icon: 'music-note',
                bg: colors.warningBg,
                onPress: async () => {
                  try {
                    await robotTrigger('dance');
                  } catch {
                    /* ignore */
                  }
                },
              },
              {
                key: 'ctl',
                label: 'Control',
                sub: 'Tiến / quay / dừng',
                icon: 'gamepad-variant',
                bg: colors.purpleBg,
                onPress: () => setCtrl(true),
              },
            ]}
          />

          <Pressable
            style={styles.lastBubble}
            onPress={() => navigation.navigate('Chat')}>
            <Text style={styles.lastLabel}>Chat gần nhất</Text>
            <Text style={styles.lastUser} numberOfLines={2}>
              {state.lastUser ? truncate(state.lastUser, 120) : '—'}
            </Text>
            <Text style={styles.lastBot} numberOfLines={4}>
              {state.lastBot ? truncate(state.lastBot, 280) : 'Chưa có tin nhắn.'}
            </Text>
          </Pressable>

          <View style={styles.inputRow}>
            <TextInput
              placeholder="Nhập lệnh hoặc chat…"
              placeholderTextColor={colors.textMuted}
              style={styles.input}
              value={draft}
              onChangeText={setDraft}
              onSubmitEditing={sendQuick}
            />
            <Pressable style={styles.send} onPress={sendQuick}>
              <MaterialCommunityIcons name="send" size={22} color={colors.text} />
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
      <ControlPanel visible={ctrl} onClose={() => setCtrl(false)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  scroll: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
    gap: spacing.md,
  },
  stickyConn: {
    backgroundColor: colors.bg,
    paddingBottom: spacing.sm,
    marginHorizontal: -spacing.lg,
    paddingHorizontal: spacing.lg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.accentBg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  headerMid: { flex: 1, gap: spacing.xs },
  title: { color: colors.text, fontSize: font.h1, fontWeight: '700' },
  iconBtn: { padding: spacing.xs },
  lastBubble: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.xs,
  },
  lastLabel: {
    color: colors.textMuted,
    fontSize: font.small,
    textTransform: 'uppercase',
  },
  lastUser: { color: colors.accent, fontSize: font.body },
  lastBot: { color: colors.text, fontSize: font.body },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
  },
  input: {
    flex: 1,
    color: colors.text,
    paddingVertical: spacing.sm,
    fontSize: font.body,
  },
  send: {
    padding: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accentBg,
  },
});
