# Alpha Mini — React Native (Android)

Client HTTP cho [AlphaMiniServer](../server.py): chat Gemini qua `/chat`, camera robot, quét QR, voice `/voice/chat`, lịch sử QR.

## Chuẩn bị

- Node 18+, Android SDK (RN 0.79 template đã có `android/`).
- Máy PC chạy server + robot **cùng Wi‑Fi** với điện thoại.
- Trong **Settings**: nhập URL (`https://<IP-LAN-PC>:8000` hoặc HTTP nếu tắt SSL), token `X-Alphamini-Token` nếu server bật.

### HTTPS self-signed

Xem `src/utils/ssl.ts` và `android/app/src/main/res/xml/network_security_config.xml`.
Có thể import chứng chỉ vào máy hoặc tạm dùng `http://` khi dev.

## Chạy

```bash
cd AlphaMiniApp
npm install --legacy-peer-deps
npm run android
```

Metro: `npm start`.

## Native deps chính

- `@react-navigation/*`, `axios`, `@react-native-async-storage/async-storage`
- `react-native-vision-camera` + `react-native-nitro-modules` + `react-native-nitro-image` — preview + quét QR (native ML Kit pipeline của VisionCamera v5)
- `react-native-reanimated`, `react-native-gesture-handler`, `react-native-safe-area-context`, `react-native-screens`
- `react-native-image-picker`, `react-native-audio-recorder-player`, `react-native-vector-icons`

Package Android: `com.alphaminiapp`.

## Troubleshooting

Xem [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Metro / màn hình đỏ “Unable to load script”, build Android, `adb reverse`, bundle offline.
