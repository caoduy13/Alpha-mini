import React from 'react';
import {
  Linking,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Clipboard from '@react-native-clipboard/clipboard';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { isUrl } from '../utils/format';
import { colors, font, radius, spacing } from '../theme';

export type QRResultVM =
  | {
      ok: true;
      text: string;
      format?: string;
      reply?: string;
      fed_to_chat?: boolean;
      duplicate?: boolean;
    }
  | { ok: false; message: string };

export function QRResultCard({ result }: { result: QRResultVM | null }) {
  if (!result) {
    return null;
  }
  if (!result.ok) {
    return (
      <View style={[styles.card, styles.errCard]}>
        <MaterialCommunityIcons
          name="alert-circle"
          size={22}
          color={colors.error}
        />
        <Text style={styles.errMsg}>{result.message}</Text>
      </View>
    );
  }

  const url = isUrl(result.text);

  return (
    <View style={[styles.card, styles.okCard]}>
      <View style={styles.row}>
        <MaterialCommunityIcons
          name="check-circle"
          size={22}
          color={colors.success}
        />
        <Text style={styles.fmt}>
          {result.format || 'QR'} {result.duplicate ? '(trùng)' : ''}
        </Text>
      </View>
      <Text selectable style={styles.mono}>
        {result.text}
      </Text>
      <View style={styles.actions}>
        {url ? (
          <Pressable
            style={styles.btn}
            onPress={() => Linking.openURL(result.text)}>
            <Text style={styles.btnTxt}>Mở link</Text>
          </Pressable>
        ) : null}
        <Pressable
          style={styles.btn}
          onPress={() => Clipboard.setString(result.text)}>
          <Text style={styles.btnTxt}>Copy</Text>
        </Pressable>
      </View>
      {result.fed_to_chat && result.reply ? (
        <View style={styles.gem}>
          <View style={styles.gemHead}>
            <MaterialCommunityIcons
              name="star-four-points"
              size={16}
              color={colors.accent}
            />
            <Text style={styles.gemPill}>Gemini</Text>
          </View>
          <Text style={styles.gemTxt}>{result.reply}</Text>
        </View>
      ) : result.reply && result.reply !== result.text ? (
        <Text style={styles.subReply}>{result.reply}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.sm,
  },
  okCard: {
    borderColor: colors.success,
    backgroundColor: colors.successBg,
  },
  errCard: {
    borderColor: colors.error,
    backgroundColor: colors.errorBg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  errMsg: { flex: 1, color: colors.error, fontSize: font.body },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  fmt: { color: colors.textMuted, fontSize: font.small },
  mono: { color: colors.text, fontFamily: 'monospace', fontSize: font.body },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  btn: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accentBg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  btnTxt: { color: colors.accent, fontWeight: '600', fontSize: font.label },
  gem: {
    marginTop: spacing.sm,
    padding: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  gemHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  gemPill: {
    color: colors.accent,
    fontSize: font.small,
    fontWeight: '700',
  },
  gemTxt: {
    marginTop: spacing.xs,
    color: colors.textMuted,
    fontStyle: 'italic',
    fontSize: font.body,
  },
  subReply: { color: colors.textMuted, fontSize: font.body },
});
