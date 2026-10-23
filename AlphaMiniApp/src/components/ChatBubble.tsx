import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, font, radius, spacing } from '../theme';

export function ChatBubble({
  role,
  text,
  timeLabel,
  badge,
}: {
  role: 'user' | 'bot';
  text: string;
  timeLabel: string;
  badge?: string;
}) {
  const isUser = role === 'user';
  return (
    <View style={[styles.wrap, isUser ? styles.alignRight : styles.alignLeft]}>
      <View
        style={[
          styles.bubble,
          isUser ? styles.userBubble : styles.botBubble,
        ]}>
        <Text style={styles.text}>{text}</Text>
        {badge ? (
          <View style={styles.badge}>
            <Text style={styles.badgeTxt}>{badge}</Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.time}>{timeLabel}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginVertical: spacing.xs,
    maxWidth: '92%',
  },
  alignRight: { alignSelf: 'flex-end', alignItems: 'flex-end' },
  alignLeft: { alignSelf: 'flex-start', alignItems: 'flex-start' },
  bubble: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.xl,
  },
  userBubble: {
    backgroundColor: colors.accentBg,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    borderBottomLeftRadius: radius.xl,
    borderBottomRightRadius: radius.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  botBubble: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.sm,
    borderTopRightRadius: radius.xl,
    borderBottomRightRadius: radius.xl,
    borderBottomLeftRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  text: { color: colors.text, fontSize: font.body },
  time: {
    marginTop: 2,
    fontSize: font.small,
    color: colors.textMuted,
  },
  badge: {
    marginTop: spacing.xs,
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.full,
    backgroundColor: colors.purpleBg,
  },
  badgeTxt: {
    color: colors.purple,
    fontSize: font.small,
    fontWeight: '600',
  },
});
