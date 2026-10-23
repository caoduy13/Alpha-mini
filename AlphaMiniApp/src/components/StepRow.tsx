import React from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import type { ChainStep } from '../connection/chain';
import { colors, font, spacing } from '../theme';

type Props = { step: ChainStep };

export function StepRow({ step }: Props) {
  let icon: string;
  let iconColor = colors.textMuted;
  switch (step.status) {
    case 'pending':
      icon = '○';
      break;
    case 'running':
      icon = '⟳';
      iconColor = colors.accent;
      break;
    case 'success':
      icon = '✓';
      iconColor = colors.success;
      break;
    case 'failed':
      icon = '✗';
      iconColor = colors.error;
      break;
    case 'skipped':
      icon = '—';
      break;
    default:
      icon = '○';
  }

  return (
    <View style={styles.row}>
      <View style={styles.iconCol}>
        {step.status === 'running' ? (
          <ActivityIndicator size="small" color={colors.accent} />
        ) : (
          <Text style={[styles.icon, { color: iconColor }]}>{icon}</Text>
        )}
      </View>
      <View style={styles.body}>
        <Text
          style={[
            styles.label,
            step.status === 'skipped' && styles.labelSkipped,
          ]}>
          {step.label}
        </Text>
        {step.detail ? (
          <Text style={styles.detail} numberOfLines={3}>
            {step.detail}
          </Text>
        ) : null}
        {step.status === 'failed' && step.error ? (
          <Text style={styles.err}>{step.error.message}</Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  iconCol: { width: 28, alignItems: 'center', paddingTop: 2 },
  icon: { fontSize: 16, fontWeight: '700' },
  body: { flex: 1, minWidth: 0 },
  label: { color: colors.text, fontSize: font.body, fontWeight: '600' },
  labelSkipped: { color: colors.textMuted, fontStyle: 'italic', fontWeight: '500' },
  detail: { color: colors.textMuted, fontSize: font.small, marginTop: 2 },
  err: { color: colors.error, fontSize: font.small, marginTop: 4 },
});
