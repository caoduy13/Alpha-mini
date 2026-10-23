import Clipboard from '@react-native-clipboard/clipboard';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import type { ConnError, ConnErrorKind } from '../api/client';
import { colors, font, radius, spacing } from '../theme';

const kindIcon: Record<ConnErrorKind, string> = {
  cleartext: 'shield-alert',
  cert: 'lock-alert',
  refused: 'lan-disconnect',
  timeout: 'timer-sand',
  dns: 'map-marker-off-outline',
  unauthorized: 'key-alert',
  server: 'dns-outline',
  unknown: 'alert-circle-outline',
};

function kindColor(k: ConnErrorKind): string {
  switch (k) {
    case 'cleartext':
    case 'cert':
    case 'timeout':
      return colors.warning;
    case 'refused':
    case 'dns':
    case 'server':
    case 'unauthorized':
      return colors.error;
    default:
      return colors.textMuted;
  }
}

type Props = {
  error: ConnError | null;
  onDismiss: () => void;
  onRetry?: () => void;
};

export function ErrorCard({ error, onDismiss, onRetry }: Props) {
  if (!error) {
    return null;
  }
  const c = kindColor(error.kind);
  const icon = kindIcon[error.kind];

  return (
    <View style={[styles.card, { borderColor: c }]}>
      <View style={styles.headRow}>
        <MaterialCommunityIcons
          // glyph name từ map động theo ConnErrorKind
          name={icon as React.ComponentProps<typeof MaterialCommunityIcons>['name']}
          size={22}
          color={c}
        />
        <Text style={[styles.title, { color: c }]}>{error.message}</Text>
      </View>
      {error.fixHint ? (
        <Text style={styles.hint}>{error.fixHint}</Text>
      ) : null}
      <View style={styles.actions}>
        {onRetry ? (
          <Pressable
            style={[styles.btn, { backgroundColor: colors.accent }]}
            onPress={onRetry}>
            <Text style={styles.btnTxtPrimary}>Thử lại</Text>
          </Pressable>
        ) : null}
        <Pressable
          style={styles.btnSec}
          onPress={() => Clipboard.setString(error.detail)}>
          <Text style={styles.btnSecTxt}>Copy log</Text>
        </Pressable>
        <Pressable style={styles.btnSec} onPress={onDismiss}>
          <Text style={styles.btnSecTxt}>Đóng</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.errorBg,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.sm,
  },
  headRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  title: {
    flex: 1,
    fontSize: font.title,
    fontWeight: '700',
  },
  hint: {
    color: colors.textMuted,
    fontSize: font.body,
    lineHeight: 20,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  btn: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
  },
  btnTxtPrimary: {
    color: colors.text,
    fontWeight: '700',
    fontSize: font.body,
  },
  btnSec: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.card,
  },
  btnSecTxt: {
    color: colors.text,
    fontWeight: '600',
    fontSize: font.body,
  },
});
