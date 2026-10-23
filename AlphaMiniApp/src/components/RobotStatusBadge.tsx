import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, font, radius, spacing } from '../theme';

export function RobotStatusBadge({ online }: { online: boolean }) {
  return (
    <View
      style={[
        styles.wrap,
        { backgroundColor: online ? colors.successBg : colors.errorBg },
      ]}>
      <MaterialCommunityIcons
        name={online ? 'lan-connect' : 'lan-disconnect'}
        size={14}
        color={online ? colors.success : colors.error}
      />
      <Text
        style={[
          styles.txt,
          { color: online ? colors.success : colors.error },
        ]}>
        {online ? 'Online' : 'Offline'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
  },
  txt: { fontSize: font.small, fontWeight: '600' },
});
