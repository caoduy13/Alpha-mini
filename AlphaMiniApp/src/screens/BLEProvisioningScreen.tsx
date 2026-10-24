import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { BleStageList } from '../components/BleStageList';
import { useApp } from '../context/AppContext';
import { getBleManager } from '../ble/manager';
import { State } from 'react-native-ble-plx';
import { requestBlePermissions } from '../ble/permissions';
import { useBleProvisioning } from '../hooks/useBleProvisioning';
import type { RootStackParamList } from '../navigation/types';
import { colors, font, radius, spacing } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'BLEProvisioning'>;

export function BLEProvisioningScreen({ navigation }: Props) {
  const { lastSSID, setLastSSID, setOnboardingDone } = useApp();
  const {
    stage,
    devices,
    logs,
    error,
    resultIp,
    lastErrorStage,
    startScan,
    stopScanOnly,
    provision,
    cancel,
  } = useBleProvisioning();

  const [uiStep, setUiStep] = useState(1);
  const [permOk, setPermOk] = useState(false);
  const [btOn, setBtOn] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [ssid, setSsid] = useState(lastSSID);
  const [password, setPassword] = useState('');
  const [rememberSSID, setRememberSSID] = useState(true);
  const [showPw, setShowPw] = useState(false);

  useEffect(() => {
    setSsid(prev => (prev ? prev : lastSSID));
  }, [lastSSID]);

  useEffect(() => {
    const sub = getBleManager().onStateChange(state => {
      setBtOn(state === State.PoweredOn);
    }, true);
    return () => sub.remove();
  }, []);

  const refreshPerm = useCallback(async () => {
    const r = await requestBlePermissions();
    setPermOk(r.ok);
  }, []);

  useEffect(() => {
    void refreshPerm();
  }, [refreshPerm]);

  useEffect(() => {
    if (uiStep === 1 && permOk && btOn) {
      const t = setTimeout(() => setUiStep(2), 450);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [uiStep, permOk, btOn]);

  useEffect(() => {
    if (uiStep === 2) {
      void startScan();
      return () => stopScanOnly();
    }
    return undefined;
  }, [uiStep, startScan, stopScanOnly]);

  const logsText = useMemo(() => logs.join('\n'), [logs]);

  async function onSendWifi() {
    if (!selectedId || !ssid.trim()) {
      return;
    }
    setUiStep(4);
    if (rememberSSID) {
      await setLastSSID(ssid.trim());
    }
    await provision(selectedId, ssid.trim(), password);
  }

  async function onSuccessNext() {
    await setOnboardingDone(true);
    navigation.reset({
      index: 1,
      routes: [{ name: 'Main' }, { name: 'Settings' }],
    });
  }

  function onRetryFromFail() {
    void (async () => {
      await cancel();
      setUiStep(2);
      setSelectedId(null);
    })();
  }

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} hitSlop={12} style={styles.back}>
          <MaterialCommunityIcons name="arrow-left" size={22} color={colors.text} />
        </Pressable>
        <Text style={styles.headerTitle}>Cấp WiFi robot</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.stepHint}>Bước {uiStep}/4</Text>

        {uiStep === 1 ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Quyền & Bluetooth</Text>
            {!permOk ? (
              <Text style={styles.muted}>Cần quyền Bluetooth để tìm robot MINI_</Text>
            ) : (
              <Text style={styles.ok}>Đã có quyền BLE</Text>
            )}
            {!btOn ? (
              <Text style={styles.muted}>Bluetooth đang tắt — hãy bật trong Cài đặt.</Text>
            ) : (
              <Text style={styles.ok}>Bluetooth đã bật</Text>
            )}
            <View style={styles.rowBtns}>
              {!permOk ? (
                <Pressable style={styles.btnAccent} onPress={refreshPerm}>
                  <Text style={styles.btnAccentTxt}>Cấp quyền</Text>
                </Pressable>
              ) : null}
              {!btOn ? (
                <Pressable
                  style={styles.btnSecondary}
                  onPress={() =>
                    Linking.openSettings().catch(() => undefined)
                  }>
                  <Text style={styles.btnSecondaryTxt}>Mở Cài đặt</Text>
                </Pressable>
              ) : null}
            </View>
            {Platform.OS === 'android' && !permOk ? (
              <Text style={styles.hintSmall}>
                Android 12+: cần BLUETOOTH_SCAN / CONNECT. Dưới Android 12: vị trí chính
                xác.
              </Text>
            ) : null}
          </View>
        ) : null}

        {uiStep === 2 ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Tìm robot</Text>
            {stage === 'scanning' ? (
              <View style={styles.row}>
                <ActivityIndicator color={colors.accent} />
                <Text style={styles.body}>Đang quét BLE (~15s)...</Text>
              </View>
            ) : (
              <Text style={styles.body}>Chọn robot trong danh sách.</Text>
            )}
            {error ? (
              <Text accessibilityRole="alert" style={styles.failTxt}>{error}</Text>
            ) : null}
            <FlatList
              data={devices}
              keyExtractor={item => item.id}
              scrollEnabled={false}
              ListEmptyComponent={
                stage !== 'scanning' ? (
                  <Text style={styles.muted}>
                    Không thấy robot MINI_. Robot đã bật và gần điện thoại (&lt;5m)?
                  </Text>
                ) : null
              }
              renderItem={({ item }) => (
                <Pressable
                  style={styles.deviceRow}
                  onPress={() => {
                    setSelectedId(item.id);
                    setUiStep(3);
                  }}>
                  <MaterialCommunityIcons name="robot" size={22} color={colors.accent} />
                  <View style={styles.deviceMid}>
                    <Text style={styles.deviceName}>{item.name}</Text>
                    <Text style={styles.rssi}>RSSI {item.rssi}</Text>
                  </View>
                  <MaterialCommunityIcons name="chevron-right" size={22} color={colors.textMuted} />
                </Pressable>
              )}
            />
            <Pressable style={styles.linkBtn} onPress={() => void startScan()}>
              <Text style={styles.linkTxt}>Quét lại</Text>
            </Pressable>
          </View>
        ) : null}

        {uiStep === 3 ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>WiFi nhà bạn</Text>
            <Text style={styles.label}>SSID</Text>
            <TextInput
              value={ssid}
              onChangeText={setSsid}
              placeholder="Tên WiFi"
              placeholderTextColor={colors.textMuted}
              style={styles.input}
              autoCapitalize="none"
              autoCorrect={false}
            />
            {lastSSID ? (
              <Pressable onPress={() => setSsid(lastSSID)}>
                <Text style={styles.linkTxt}>Điền SSID đã lưu</Text>
              </Pressable>
            ) : null}
            <Text style={[styles.label, { marginTop: spacing.sm }]}>Mật khẩu</Text>
            <View style={styles.pwRow}>
              <TextInput
                value={password}
                onChangeText={setPassword}
                placeholder="Mật khẩu WiFi"
                placeholderTextColor={colors.textMuted}
                style={[styles.input, styles.inputPw]}
                secureTextEntry={!showPw}
                autoCapitalize="none"
              />
              <Pressable onPress={() => setShowPw(v => !v)} style={styles.eye}>
                <MaterialCommunityIcons
                  name={showPw ? 'eye-off' : 'eye'}
                  size={22}
                  color={colors.textMuted}
                />
              </Pressable>
            </View>
            <View style={styles.switchRow}>
              <Text style={styles.body}>Lưu SSID cho lần sau</Text>
              <Switch
                value={rememberSSID}
                onValueChange={setRememberSSID}
                thumbColor={rememberSSID ? colors.accent : colors.textMuted}
              />
            </View>
            <Pressable style={styles.btnAccent} onPress={() => void onSendWifi()}>
              <Text style={styles.btnAccentTxt}>Gửi cho robot</Text>
            </Pressable>
            <Pressable onPress={() => setUiStep(2)}>
              <Text style={[styles.linkTxt, { marginTop: spacing.sm }]}>← Chọn robot khác</Text>
            </Pressable>
          </View>
        ) : null}

        {uiStep === 4 ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Đang cấu hình</Text>
            <BleStageList currentStage={stage} lastErrorStage={lastErrorStage} />
            {stage === 'success' ? (
              <View style={styles.successBox}>
                <MaterialCommunityIcons name="check-circle" size={28} color={colors.success} />
                <Text style={styles.successTxt}>
                  Robot đã nhận WiFi.
                  {resultIp ? ` IP gợi ý: ${resultIp}` : ''}
                </Text>
                <Pressable style={styles.btnAccent} onPress={() => void onSuccessNext()}>
                  <Text style={styles.btnAccentTxt}>Tiếp theo: cấu hình server</Text>
                </Pressable>
              </View>
            ) : null}
            {stage === 'failed' ? (
              <View style={styles.failBox}>
                <MaterialCommunityIcons name="alert-circle" size={28} color={colors.error} />
                <Text style={styles.failTxt}>{error ?? 'Lỗi không xác định'}</Text>
                <Pressable style={styles.btnSecondary} onPress={onRetryFromFail}>
                  <Text style={styles.btnSecondaryTxt}>Thử lại</Text>
                </Pressable>
              </View>
            ) : null}
            <Text style={[styles.label, { marginTop: spacing.md }]}>Log</Text>
            <ScrollView style={styles.logBox} nestedScrollEnabled>
              <Text selectable style={styles.logTxt}>
                {logsText || '—'}
              </Text>
            </ScrollView>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  back: { padding: spacing.xs },
  headerTitle: { fontSize: font.title, fontWeight: '600', color: colors.text },
  scroll: { padding: spacing.lg, paddingBottom: spacing.xxl },
  stepHint: {
    fontSize: font.small,
    color: colors.textMuted,
    marginBottom: spacing.sm,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  cardTitle: {
    fontSize: font.title,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  body: { fontSize: font.body, color: colors.text },
  muted: { fontSize: font.body, color: colors.textMuted },
  ok: { fontSize: font.body, color: colors.success },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  rowBtns: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginTop: spacing.sm },
  btnAccent: {
    backgroundColor: colors.accent,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    alignItems: 'center',
  },
  btnAccentTxt: { color: colors.bg, fontWeight: '600', fontSize: font.title },
  btnSecondary: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  btnSecondaryTxt: { color: colors.text, fontWeight: '600' },
  hintSmall: { fontSize: font.small, color: colors.textMuted },
  deviceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  deviceMid: { flex: 1 },
  deviceName: { fontSize: font.title, color: colors.text },
  rssi: { fontSize: font.small, color: colors.textMuted },
  linkBtn: { alignSelf: 'flex-start', marginTop: spacing.sm },
  linkTxt: { color: colors.accent, fontSize: font.body },
  label: { fontSize: font.label, color: colors.textMuted },
  input: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: Platform.OS === 'ios' ? spacing.md : spacing.sm,
    color: colors.text,
    backgroundColor: colors.surface,
    marginTop: spacing.xs,
  },
  pwRow: { flexDirection: 'row', alignItems: 'center' },
  inputPw: { flex: 1 },
  eye: { padding: spacing.sm },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  successBox: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.successBg,
    gap: spacing.sm,
    alignItems: 'flex-start',
  },
  successTxt: { color: colors.text, fontSize: font.body },
  failBox: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.errorBg,
    gap: spacing.sm,
    alignItems: 'flex-start',
  },
  failTxt: { color: colors.error, fontSize: font.body },
  logBox: {
    maxHeight: 160,
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    padding: spacing.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  logTxt: { fontSize: font.small, color: colors.textMuted, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
});
