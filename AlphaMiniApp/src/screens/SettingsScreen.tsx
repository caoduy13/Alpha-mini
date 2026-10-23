import Clipboard from '@react-native-clipboard/clipboard';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import axios from 'axios';
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { tryApi } from '../api/client';
import { getRobotDiagnose, getRobotScan } from '../api/endpoints';
import { ConnectionPanel } from '../components/ConnectionPanel';
import { useApp } from '../context/AppContext';
import { useSettings } from '../hooks/useSettings';
import type { RootStackParamList } from '../navigation/types';
import { colors, font, radius, spacing } from '../theme';
import { SSL_DEV_NOTES } from '../utils/ssl';

const REPO = 'https://github.com/caoduy13/Alpha-mini';

const IPV4_RE =
  /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

function isValidIPv4(s: string): boolean {
  return IPV4_RE.test(s.trim());
}

function parseServerUrl(url: string): {
  https: boolean;
  ip: string;
  port: string;
} {
  const t = url.trim();
  if (!t) {
    return { https: false, ip: '', port: '8000' };
  }
  const withProto = /^https?:\/\//i.test(t) ? t : `http://${t}`;
  try {
    const u = new URL(withProto);
    const https = u.protocol === 'https:';
    const port = u.port || (https ? '443' : '8000');
    return { https, ip: u.hostname, port };
  } catch {
    return { https: false, ip: '', port: '8000' };
  }
}

function buildServerUrl(https: boolean, ip: string, port: string): string {
  const p = (port.trim() || '8000').replace(/^\s+|\s+$/g, '');
  const scheme = https ? 'https' : 'http';
  const host = ip.trim();
  return `${scheme}://${host}:${p}`;
}

function subnetPrefixFromIp(ip: string): string | null {
  if (!isValidIPv4(ip)) {
    return null;
  }
  const parts = ip.trim().split('.');
  return parts.length === 4 ? `${parts[0]}.${parts[1]}.${parts[2]}` : null;
}

type Props = NativeStackScreenProps<RootStackParamList, 'Settings'>;

export function SettingsScreen({ navigation }: Props) {
  const { prefs, persist, reload } = useSettings();
  const { lastSSID, setLastSSID, connection, refreshConnection } = useApp();

  const [useHttps, setUseHttps] = useState(false);
  const [ip, setIp] = useState('');
  const [port, setPort] = useState('8000');
  const [token, setToken] = useState('');
  const [tokenOpen, setTokenOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [scanBusy, setScanBusy] = useState(false);
  const [scanHits, setScanHits] = useState<string[]>([]);

  useEffect(() => {
    const p = parseServerUrl(prefs.serverUrl);
    setUseHttps(p.https);
    setIp(p.ip);
    setPort(p.port || '8000');
    setToken(prefs.skillToken);
  }, [prefs.serverUrl, prefs.skillToken]);

  useFocusEffect(
    useCallback(() => {
      void refreshConnection();
      const id = setInterval(() => void refreshConnection(), 30_000);
      return () => clearInterval(id);
    }, [refreshConnection]),
  );

  const ipOk = ip.trim().length === 0 || isValidIPv4(ip);
  const portNum = Number(port.trim());
  const portOk =
    port.trim().length === 0 || (Number.isInteger(portNum) && portNum >= 1 && portNum <= 65535);

  async function applyServerToStorage() {
    const built = buildServerUrl(useHttps, ip, port);
    await persist({ serverUrl: built, skillToken: token.trim() });
    await reload();
  }

  async function onSave() {
    if (!isValidIPv4(ip)) {
      Alert.alert('IP không hợp lệ', 'Nhập địa chỉ IPv4 (vd. 192.168.1.5).');
      return;
    }
    if (!portOk) {
      Alert.alert('Port không hợp lệ', 'Dùng số từ 1 đến 65535.');
      return;
    }
    await applyServerToStorage();
    const ok = await refreshConnection();
    if (!ok) {
      Alert.alert(
        'Chưa thấy server',
        'Đã lưu URL. Bấm «Kết nối» trong panel bên dưới để kiểm tra đầy đủ.',
      );
      return;
    }
    Alert.alert('Đã lưu', 'Cấu hình server đã được cập nhật.');
  }

  async function onDiagnoseAdvanced() {
    const r = await tryApi(() => getRobotDiagnose());
    if (!r.ok) {
      Alert.alert('Lỗi', r.error.message);
      return;
    }
    Alert.alert('Chẩn đoán', JSON.stringify(r.data).slice(0, 900));
  }

  async function onScanLanAdvanced() {
    const r = await tryApi(() => getRobotScan());
    if (!r.ok) {
      Alert.alert('Lỗi', r.error.message);
      return;
    }
    Alert.alert('Quét LAN', JSON.stringify(r.data).slice(0, 900));
  }

  async function onScanServers() {
    setScanHits([]);
    const prefix = subnetPrefixFromIp(ip);
    if (!prefix) {
      Alert.alert(
        'Cần IP hợp lệ',
        'Nhập IPv4 trong mạng LAN (vd. 192.168.1.5) để quét dải /24.',
      );
      return;
    }
    const p = Number(port.trim()) || 8000;
    const scheme = useHttps ? 'https' : 'http';
    const headers =
      token.trim().length > 0
        ? { 'X-Alphamini-Token': token.trim() }
        : undefined;

    setScanBusy(true);
    try {
      const found: string[] = [];
      const ips = Array.from({ length: 254 }, (_, i) => `${prefix}.${i + 1}`);
      const chunk = 20;
      for (let i = 0; i < ips.length; i += chunk) {
        const batch = ips.slice(i, i + chunk);
        const results = await Promise.all(
          batch.map(async host => {
            try {
              const res = await axios.get(`${scheme}://${host}:${p}/status`, {
                timeout: 500,
                validateStatus: s => s === 200,
                headers,
              });
              return res.status === 200 ? host : null;
            } catch {
              return null;
            }
          }),
        );
        for (const h of results) {
          if (h) {
            found.push(h);
          }
        }
      }
      setScanHits(found);
      if (found.length === 0) {
        Alert.alert('Quét xong', 'Không thấy server /status trên dải mạng này.');
      }
    } finally {
      setScanBusy(false);
    }
  }

  function applyFoundServer(host: string) {
    setIp(host);
    setScanHits([]);
  }

  async function onExportLogs() {
    const payload = {
      at: new Date().toISOString(),
      connection,
      form: { useHttps, ip, port, tokenSet: token.trim().length > 0 },
      prefs: {
        autoChatGemini: prefs.autoChatGemini,
        robotSpeakReplies: prefs.robotSpeakReplies,
      },
    };
    await Clipboard.setString(JSON.stringify(payload, null, 2));
    Alert.alert('Đã copy', 'Nội dung diagnostic đã vào clipboard.');
  }

  async function onClearCache() {
    await setLastSSID('');
    Alert.alert('Đã xóa', 'Đã xóa SSID WiFi robot đã lưu (cache nhẹ).');
  }

  async function onResetSettings() {
    Alert.alert(
      'Reset cài đặt?',
      'Xóa URL server, token và đưa toggle về mặc định.',
      [
        { text: 'Huỷ', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: async () => {
            await persist({
              serverUrl: '',
              skillToken: '',
              autoChatGemini: true,
              robotSpeakReplies: true,
            });
            await reload();
            setUseHttps(false);
            setIp('');
            setPort('8000');
            setToken('');
            void refreshConnection();
          },
        },
      ],
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['left', 'right']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled">
        <Text style={styles.section}>Server</Text>

        <View style={styles.rowBetween}>
          <Text style={styles.lbl}>Giao thức</Text>
          <View style={styles.row}>
            <Text style={styles.protoLbl}>HTTP</Text>
            <Switch
              value={useHttps}
              onValueChange={setUseHttps}
              thumbColor={colors.text}
              trackColor={{ false: colors.border, true: colors.accent }}
            />
            <Text style={styles.protoLbl}>HTTPS</Text>
          </View>
        </View>

        <Text style={styles.lbl}>IP máy chủ (IPv4)</Text>
        <TextInput
          style={[styles.input, !ipOk && styles.inputBad]}
          placeholder="192.168.1.5"
          placeholderTextColor={colors.textMuted}
          autoCapitalize="none"
          keyboardType="decimal-pad"
          value={ip}
          onChangeText={setIp}
        />
        <Text style={styles.inlineHint}>
          {ip.trim().length === 0
            ? 'Bắt buộc trước khi Lưu / Test.'
            : ipOk
              ? '✓ Định dạng IPv4 hợp lệ'
              : '✗ IPv4 không hợp lệ'}
        </Text>

        <Text style={styles.lbl}>Port</Text>
        <TextInput
          style={[styles.input, !portOk && styles.inputBad]}
          placeholder="8000"
          placeholderTextColor={colors.textMuted}
          autoCapitalize="none"
          keyboardType="number-pad"
          value={port}
          onChangeText={setPort}
        />

        <Text style={styles.helper}>
          IP của PC chạy server. Trên Windows: `ipconfig` → IPv4 Address. Điện
          thoại và PC nên cùng WiFi.
        </Text>

        <View style={styles.scanRow}>
          <Pressable
            style={[styles.btnOutline, scanBusy && styles.btnDisabled]}
            onPress={() => void onScanServers()}
            disabled={scanBusy}>
            {scanBusy ? (
              <ActivityIndicator color={colors.accent} />
            ) : (
              <Text style={styles.btnOutlineTxt}>Quét mạng tìm server</Text>
            )}
          </Pressable>
        </View>
        {scanHits.length > 0 ? (
          <View style={styles.hitList}>
            <Text style={styles.lbl}>Tìm thấy:</Text>
            {scanHits.map(h => (
              <Pressable key={h} onPress={() => applyFoundServer(h)} style={styles.hitChip}>
                <Text style={styles.hitChipTxt}>
                  {h}:{port.trim() || '8000'}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : null}

        <Pressable
          onPress={() => setTokenOpen(o => !o)}
          style={styles.tokenToggle}>
          <Text style={styles.lbl}>
            X-Alphamini-Token {tokenOpen ? '▼' : '▶'} (tuỳ chọn)
          </Text>
        </Pressable>
        {tokenOpen ? (
          <TextInput
            style={styles.input}
            placeholder="Để trống nếu server không bật token"
            placeholderTextColor={colors.textMuted}
            secureTextEntry
            value={token}
            onChangeText={setToken}
          />
        ) : null}

        <Pressable style={styles.btnPrimary} onPress={() => void onSave()}>
          <Text style={styles.btnPrimaryTxt}>Lưu</Text>
        </Pressable>

        <ConnectionPanel compact />

        <Text style={styles.section}>WiFi (BLE)</Text>
        <Text style={styles.hint}>
          SSID đã lưu: {lastSSID ? lastSSID : '(trống)'}
        </Text>
        <Pressable
          style={styles.btnOutline}
          onPress={() => navigation.navigate('BLEProvisioning')}>
          <Text style={styles.btnOutlineTxt}>Cấu hình lại WiFi robot</Text>
        </Pressable>

        <Text style={styles.section}>QR scan</Text>
        <View style={styles.switchRow}>
          <Text style={styles.lbl}>Auto-chat Gemini</Text>
          <Switch
            value={prefs.autoChatGemini}
            onValueChange={v => persist({ autoChatGemini: v })}
            thumbColor={colors.text}
            trackColor={{ false: colors.border, true: colors.accent }}
          />
        </View>
        <View style={styles.switchRow}>
          <Text style={styles.lbl}>Robot đọc to kết quả</Text>
          <Switch
            value={prefs.robotSpeakReplies}
            onValueChange={v => persist({ robotSpeakReplies: v })}
            thumbColor={colors.text}
            trackColor={{ false: colors.border, true: colors.success }}
          />
        </View>

        <Pressable
          onPress={() => setAdvancedOpen(o => !o)}
          style={styles.advHeader}>
          <Text style={styles.section}>
            Nâng cao {advancedOpen ? '▼' : '▶'}
          </Text>
        </Pressable>
        {advancedOpen ? (
          <View style={styles.advBox}>
            <Text style={styles.advHint}>{SSL_DEV_NOTES}</Text>
            <Text style={styles.mono}>
              GET /status{'\n'}
              POST /robot/connect{'\n'}
              POST /robot/reconnect{'\n'}
              GET /robot/diagnose{'\n'}
              GET /robot/scan
            </Text>
            <Pressable
              style={styles.btnOutline}
              onPress={() => void onDiagnoseAdvanced()}>
              <Text style={styles.btnOutlineTxt}>Chẩn đoán robot</Text>
            </Pressable>
            <Pressable
              style={styles.btnOutline}
              onPress={() => void onScanLanAdvanced()}>
              <Text style={styles.btnOutlineTxt}>Quét LAN robot</Text>
            </Pressable>
            <Pressable style={styles.btnOutline} onPress={() => void onExportLogs()}>
              <Text style={styles.btnOutlineTxt}>Export logs (copy)</Text>
            </Pressable>
            <Pressable style={styles.btnOutline} onPress={() => void onClearCache()}>
              <Text style={styles.btnOutlineTxt}>Clear cache (SSID)</Text>
            </Pressable>
            <Pressable
              style={[styles.btnOutline, styles.dangerOutline]}
              onPress={() => void onResetSettings()}>
              <Text style={[styles.btnOutlineTxt, styles.dangerTxt]}>
                Reset settings
              </Text>
            </Pressable>
          </View>
        ) : null}

        <Text style={styles.section}>About</Text>
        <Text style={styles.ver}>Alpha Mini app v1.0.0</Text>
        <Pressable onPress={() => void Linking.openURL(REPO)}>
          <Text style={styles.link}>{REPO}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  scroll: { padding: spacing.lg, gap: spacing.md, paddingBottom: 48 },
  section: {
    marginTop: spacing.sm,
    color: colors.text,
    fontSize: font.title,
    fontWeight: '700',
  },
  helper: {
    color: colors.textMuted,
    fontSize: font.small,
    lineHeight: 18,
  },
  hint: { color: colors.textMuted, fontSize: font.small },
  lbl: { color: colors.textMuted, fontSize: font.label },
  inlineHint: { color: colors.textMuted, fontSize: font.small },
  input: {
    backgroundColor: colors.card,
    borderRadius: radius.md,
    padding: spacing.md,
    color: colors.text,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    fontSize: font.body,
  },
  inputBad: { borderColor: colors.error },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  protoLbl: { color: colors.text, fontSize: font.small },
  scanRow: { marginTop: spacing.xs },
  hitList: { gap: spacing.xs },
  hitChip: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accentBg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.full,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  hitChipTxt: { color: colors.accent, fontWeight: '600' },
  tokenToggle: { marginTop: spacing.xs },
  btnPrimary: {
    backgroundColor: colors.accent,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    alignItems: 'center',
  },
  btnPrimaryTxt: { color: colors.text, fontWeight: '700', fontSize: font.body },
  btnOutline: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.accentBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnOutlineTxt: {
    color: colors.accent,
    fontWeight: '600',
    textAlign: 'center',
    fontSize: font.body,
  },
  btnDisabled: { opacity: 0.6 },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.card,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  advHeader: { marginTop: 0 },
  advBox: { gap: spacing.md },
  advHint: { color: colors.textMuted, fontSize: font.small },
  mono: {
    color: colors.textMuted,
    fontSize: font.small,
    fontFamily: 'monospace',
  },
  dangerOutline: { borderColor: colors.error },
  dangerTxt: { color: colors.error },
  ver: { color: colors.textMuted, fontSize: font.body },
  link: { color: colors.accent, fontSize: font.body, marginTop: spacing.xs },
});
