# Troubleshooting

## Màn hình đỏ "Unable to load script. Make sure you're either running Metro..."

**Nguyên nhân:** debug build không nhúng JS bundle vào APK — app load JS từ Metro server (port 8081) lúc runtime. Lỗi này nghĩa là device không kết nối được tới Metro.

**Fix nhanh (USB device — cách phổ biến nhất):**

```powershell
adb reverse tcp:8081 tcp:8081
adb reverse --list   # verify
```

Lưu ý: mỗi lần rút/cắm USB hoặc reboot device đều phải chạy lại lệnh `adb reverse`.

**Hoặc dùng script tiện trong repo:**

```powershell
cd AlphaMiniApp
.\scripts\dev-android.ps1            # adb reverse + start Metro
.\scripts\dev-android.ps1 -ResetCache   # khi đổi metro/babel config
.\scripts\dev-android.ps1 -NoMetro      # chỉ reverse, Metro chạy terminal khác
```

**Verify Metro reachable từ device:**

```powershell
adb shell curl http://localhost:8081/status
# expect: packager-status:running
```

**Emulator:** dùng `10.0.2.2:8081` thay vì `localhost`. Emulator của Android Studio thường tự route, không cần `adb reverse`.

**Khác mạng WiFi (device và PC):** Shake device → **Dev Settings** → **Debug server host & port for device** → nhập `<IP_PC>:8081` (lấy IP bằng `ipconfig`).

**Bundle JS vào APK (chạy offline, mất hot reload — chỉ dùng khi đi demo):**

```powershell
cd AlphaMiniApp
mkdir android\app\src\main\assets -ErrorAction SilentlyContinue
npx react-native bundle `
  --platform android `
  --dev false `
  --entry-file index.js `
  --bundle-output android/app/src/main/assets/index.android.bundle `
  --assets-dest android/app/src/main/res
cd android
.\gradlew.bat :app:assembleDebug
```

APK sau đó load bundle từ `assets/`, không cần Metro.

## Build Android — các fix đã áp (tham khảo)

| Vấn đề | Fix |
|--------|-----|
| AGP 8.9.2 vs Android Studio cũ | Nâng AS lên Meerkat Feature Drop 2024.3.2 |
| react-native-screens C++ 5-param interface | Patch `RNSScreenShadowNodeCommitHook.h/.cpp` bỏ `ShadowTreeCommitOptions` |
| @react-native/codegen không hiểu TSQualifiedName | Patch `parser.js`, `parseTopLevelType.js`, `componentsUtils.js` |
| Async Storage v3 Maven repo thiếu | Thêm `local_repo` trong `build.gradle` |
| Kotlin 2.0.x / KSP mismatch | `kotlinVersion=2.1.21` |
| audio-recorder-player v4 CMake Windows | Hạ xuống `3.6.14` |
| Codegen chạy sau CMake | Hook `gradle.projectsEvaluated` trong `build.gradle` |
| Patches bền vững | `patch-package` + `postinstall` script trong `package.json` |

**Build command:**

```powershell
$env:JAVA_HOME="C:\Program Files\Android\Android Studio\jbr"
cd AlphaMiniApp\android
.\gradlew.bat :app:assembleDebug --no-daemon
```
