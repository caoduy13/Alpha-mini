import React from 'react';
import {
  Alert,
  FlatList,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Clipboard from '@react-native-clipboard/clipboard';
import { SafeAreaView } from 'react-native-safe-area-context';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { useQRHistory } from '../hooks/useQRHistory';
import { colors, font, radius, spacing } from '../theme';
import { isUrl, truncate } from '../utils/format';

function sourceIcon(src: string): string {
  const s = src.toLowerCase();
  if (s === 'robot') {
    return 'robot';
  }
  if (s === 'upload') {
    return 'upload';
  }
  return 'cellphone';
}

export function HistoryScreen() {
  const { items, loading, filter, setFilter, stats, refresh, clearRemote } =
    useQRHistory();

  function confirmClear() {
    Alert.alert('Xoá lịch sử', 'Xoá toàn bộ lịch sử QR trên server?', [
      { text: 'Huỷ', style: 'cancel' },
      {
        text: 'Xoá',
        style: 'destructive',
        onPress: () => void clearRemote(),
      },
    ]);
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Lịch sử quét</Text>
        <Pressable onPress={confirmClear} hitSlop={12}>
          <Text style={styles.clear}>Xoá hết</Text>
        </Pressable>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statCard}>
          <Text style={styles.statVal}>{stats.total}</Text>
          <Text style={styles.statLbl}>Tổng số quét</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statVal}>{stats.gemini}</Text>
          <Text style={styles.statLbl}>Đã gửi Gemini</Text>
        </View>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.filters}>
        {(
          [
            ['all', 'Tất cả'],
            ['robot', 'Robot'],
            ['camera', 'Webcam/Camera'],
            ['upload', 'Upload'],
          ] as const
        ).map(([key, label]) => {
          const on = filter === key;
          return (
            <Pressable
              key={key}
              onPress={() => setFilter(key)}
              style={[styles.pill, on && styles.pillOn]}>
              <Text style={[styles.pillTxt, on && styles.pillTxtOn]}>{label}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <FlatList
        data={items}
        keyExtractor={(item, i) => `${item.ts}-${i}`}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={refresh}
            tintColor={colors.accent}
          />
        }
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <Text style={styles.empty}>
            {loading ? 'Đang tải…' : 'Chưa có mục nào'}
          </Text>
        }
        renderItem={({ item }) => (
          <Pressable
            style={styles.row}
            onPress={() => {
              const buttons: {
                text: string;
                style?: 'cancel' | 'destructive' | 'default';
                onPress?: () => void;
              }[] = [
                {
                  text: 'Copy',
                  onPress: () => Clipboard.setString(item.text),
                },
              ];
              if (isUrl(item.text)) {
                buttons.push({
                  text: 'Mở link',
                  onPress: () => void Linking.openURL(item.text),
                });
              }
              buttons.push({ text: 'Đóng', style: 'cancel' });
              Alert.alert('Chi tiết QR', item.text, buttons);
            }}>
            <View style={styles.ico}>
              <MaterialCommunityIcons
                name={sourceIcon(item.source) as never}
                size={20}
                color={colors.accent}
              />
            </View>
            <View style={styles.mid}>
              <Text style={styles.meta}>
                {item.source} · {item.ts}
              </Text>
              <Text style={styles.qtxt} numberOfLines={3}>
                {truncate(item.text, 200)}
              </Text>
            </View>
            {item.fed_to_chat ? (
              <View style={styles.gpill}>
                <Text style={styles.gpillTxt}>Gemini</Text>
              </View>
            ) : (
              <View style={{ width: spacing.md }} />
            )}
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  title: { color: colors.text, fontSize: font.h2, fontWeight: '700' },
  clear: { color: colors.error, fontWeight: '700', fontSize: font.body },
  statsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  statVal: {
    color: colors.text,
    fontSize: font.h1,
    fontWeight: '800',
  },
  statLbl: { color: colors.textMuted, fontSize: font.small },
  filters: {
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
    paddingBottom: spacing.sm,
  },
  pill: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  pillOn: { backgroundColor: colors.accentBg, borderColor: colors.accent },
  pillTxt: { color: colors.textMuted, fontSize: font.small },
  pillTxtOn: { color: colors.accent, fontWeight: '700' },
  list: { paddingHorizontal: spacing.md, paddingBottom: spacing.xxl },
  empty: {
    textAlign: 'center',
    color: colors.textMuted,
    marginTop: spacing.xl,
    fontSize: font.body,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  ico: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.accentBg,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  mid: { flex: 1, gap: spacing.xs },
  meta: { color: colors.textMuted, fontSize: font.small },
  qtxt: { color: colors.text, fontFamily: 'monospace', fontSize: font.body },
  gpill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.full,
    backgroundColor: colors.successBg,
  },
  gpillTxt: { color: colors.success, fontSize: font.small, fontWeight: '700' },
});
