# Đặc tả BLE Alpha Mini từ APK tham chiếu

Ngày kiểm chứng: 2026-10-25 (Asia/Saigon). App đối chiếu: main `9de6ec6`.
Tài liệu chỉ đọc/đối chiếu; không triển khai giao thức mới vào app và chưa gửi frame probe tới robot.

## 1. Nguồn gốc và mức chắc chắn

File đang phân tích:
`D:/Alphamini/AlphaMiniServer-archive/RobotWifiProvisioner/MainApp.apk`.

- Kích thước: 15,923,153 byte.
- SHA-256: `5324b32f72bb45189dce2a2e852562561b1f7280fe1d74b3bdaa80bc9c3f0c2a`.
- Package: `com.ubtrobot.master.policy`.
- versionName: `V2.2.4#1024`; versionCode: `20220921`.
- minSdk 19, targetSdk 28; label `AlphaMini`.
- Manifest khai báo `android:sharedUserId="android.uid.system"`, quyền
  `com.ubtrobot.master.permission.MASTER`, `MASTER_SYSTEM_SERVICE`, receiver BOOT_COMPLETED
  và nhiều service điều khiển robot, gồm NetworkSettingService.

**Đây là APK phía robot, có triển khai GATT server.** Bằng chứng bytecode:

- `com.ubtechinc.bluetoothlibrary.UBTGattServer$4` kế thừa BluetoothGattServerCallback;
  `onCharacteristicWriteRequest()` ACK write rồi chuyển byte tới IUBTGattServerDataReceiver.
- `com.ubtechinc.bluetoothlibrary.UBTGattService.<clinit>()` khai báo chính xác:
  service `10057e66-28bd-4c3e-a030-08b4982739bc`, write/read
  `d2f9ff26-ad08-4bd3-8436-9b8f33bdea76`, indication
  `7e0dffa2-c44f-48ac-a39e-3fce46d9aabb`, CCCD `0x2902`.
- Constructor tạo BluetoothGattService/Characteristic/Descriptor. Properties indication=32,
  read/write=10; permissions characteristic=17, descriptor=16. Các bit này tự chúng không
  yêu cầu encrypted/MITM access; không được suy ra đường BLE đang mã hóa chỉ từ PDF.
- `com.ubtechinc.nets.ble.BleServer$BleDataReceiver` nhận và giải mã request; BleServer trả
  BluetoothShakeResponse. Đây không phải ví dụ client chạy trên điện thoại.

**Giới hạn provenance:** archive/README.txt ghi nguồn thư mục cũ `D:/AlphaMiniServer`, đã copy
và đối chiếu trước cleanup 3E (`b674a6f`). APK không nằm trong tree Git `42c8bb2`, không có
commit history cho đường dẫn này; `.gitignore` bỏ qua `*.apk`. Có các file `mainapp-packages.txt`
kiểu output dexdump trong cùng thư mục nhưng không tìm thấy log lệnh `adb pull`/URL tải ban đầu
trong scripts, docs hay thư mục RobotWifiProvisioner. Do đó chỉ xác nhận được chuỗi
**thư mục project cũ → archive → file có hash trên**; chưa chứng minh được nó được dump từ
chính robot đang test hay firmware hiện tại có cùng version. Không gọi đây là live device dump
đã xác thực nguồn. Không tải APK MainApp này từ Internet trong đợt phân tích.

Nguồn client đối chiếu độc lập:
[luffyjet/AlphaMiniAppDemo](https://github.com/luffyjet/AlphaMiniAppDemo),
`app/libs/alpha-mini-oversea-edu-sdk-0.0.9.aar` (89,027,387 byte).
`MiniBleProto.kt` trong AAR có cùng header/UUID; cả bốn FileDescriptorProto handshake,
Wi-Fi, CodeMao_Message, CodeMao_MessageHeader khớp hoàn toàn với descriptor trích từ MainApp.
Điều này củng cố tương thích cùng họ giao thức, chưa thay cho thử nghiệm firmware thực.
Không copy SDK/AAR vào repository; quyền sử dụng SDK cần xác nhận riêng.

## 2. Các lớp frame

### 2.1 Frame logic MiniBleProto

Nguồn: `com.ubtrobot.mini.msg_dispatcher.MiniBleProto.{pack,unpack}` trong MainApp/classes2.dex;
đối chiếu `com.ubtechinc.mini.lib.bt.protocol.b` (Compiled from MiniBleProto.kt) trong SDK client.

| Offset | Byte | Ý nghĩa đã kiểm chứng |
| --- | --- | --- |
| 0..1 | FB BF | Magic header |
| 2 | 01 | Version frame trong pack tham chiếu |
| 3..4 | uint16 big-endian L | L = số byte payload protobuf + 6; toàn frame dài L+1 |
| 5..L-2 | bytes | CodeMaoMessage.Message đã serialize |
| L-1 | 01 | Byte cố định trong pack; không phải checksum tính tổng/CRC |
| L | ED | End marker |

Unpack kiểm tra magic, độ dài/buffer đủ và ED. Không có thuật toán cộng checksum/CRC trong
pack/unpack đã đọc; byte 01 được ghi hằng và không được xác thực như một MAC mật mã.
Không áp dụng checksum của Alpha 1S chỉ vì cùng magic FB BF.
Frame có thể đến rời nhiều indication hoặc có nhiều frame trong buffer; cần parser có buffer.

### 2.2 Đóng gói từng GATT value của BLE version 1

`UBTGattServer$4.onCharacteristicWriteRequest()` tạo `Target(device, 1)`.
`BleDataReceiver$1.run()` gọi parsePacketMsg rồi lấy dataContent trước khi unpack.
Vì vậy không được write trần frame logic mà bỏ trailer:

```text
GATT value = chunk của frame logic + groupId:uint16BE + fragmentNo:uint16BE
```

- groupId được codec tham chiếu chọn ngẫu nhiên, dùng chung cho các chunk của một frame.
  Tên property trong mã là `cmdId`, nhưng đây không phải commandId protobuf.
- fragmentNo bắt đầu 1 và tăng dần. Tên property là `serialNo`; khác sendSerial của protobuf.
- Codec `devide()` trên robot và `a(byte[])` của SDK chia data theo 16 byte; cộng trailer
  4 byte thành GATT value tối đa 20 byte, vừa ATT MTU=23 (trừ ATT overhead 3).
- MTU cao hơn không tự động xóa trailer hay cho phép bỏ cơ chế phân mảnh của codec này.
- Receiver có PacketData để tích lũy fragment/buffer thiếu. Cần giữ groupId/thứ tự và
  chờ đủ frame; không parse riêng từng indication như JSON.

## 3. Schema protobuf trích trực tiếp từ MainApp

Các file là proto3; scalar không được gửi nhận giá trị mặc định. Tên package dưới đây là
Java package trong descriptor; proto nguyên bản không khai báo protobuf package.
Descriptor handshake được ghép từ string_ids 179 và 43387 của classes.dex; Wi-Fi string_id
180/classes.dex; envelope 105/classes2.dex; header 129/classes2.dex.

### 3.1 Envelope (`com.ubtechinc.codemao`)

```proto
message Message {
  MessageHeader header = 1;
  bytes bodyData = 2;
}
message MessageHeader {
  int32 commandId = 1;
  int32 sendSerial = 2;
  int32 responseSerial = 3;
  int32 versionCode = 4;
  MsgType msgType = 5;
  int32 resultCode = 6;
}
enum MsgType {
  MSG_TYPE_RESPONSE_COMPLETE = 0;
  MSG_TYPE_RESPONSE_STICKY = 1;
  MSG_TYPE_REQUEST = 2;
}
```

bodyData là protobuf của message nghiệp vụ, không phải JSON trực tiếp ở lớp này.
Ghép request/response bằng command và responseSerial, không đọc byte thứ 5 làm method.

### 3.2 Handshake (`com.ubtechinc.alpha.BluetoothHandShake`)

```proto
message BluetoothHandShakeRequest {
  string clientLan = 1;
  string clientVersionName = 2;
  int32 clientVersionCode = 3;
  string deviceCountry = 4;
  DeviceType deviceType = 5;
  string uuid = 6;
  string sessionId = 7;
}
enum DeviceType {
  UNDEFINED = 0;
  ANDROID_MOBILE = 1;
  IPHONE = 2;
  ANDROID_PAD = 3;
  IPAD = 4;
}
message BluetoothShakeResponse {
  bool isSuccess = 1;
  bool resultCode = 2;
  string sysLan = 3;
  string sysCountry = 4;
  string robotSoftVersionName = 5;
  int32 btInterfaceVersion = 6;
  string androidFirmwareVersion = 7;
  int32 errorCode = 8;
  string sessionId = 9;
  string versionInfo = 10;
}
```

`BluetoothShakeResponse.resultCode` thực sự là **bool**, không phải int32 và không cùng nghĩa
với MessageHeader.resultCode (int32). Không dùng quy tắc JSON `code == 0` để đoán thành công.

### 3.3 Wi-Fi/binding (`com.ubtechinc.alpha.BleBindOrSwitchWifi`)

```proto
message BindOrSwitchWifiRequest {
  string data = 1;
  int32 versionCode = 2;
}
message BindOrSwitchWifiResponse {
  string data = 1;
}
```

SDK client `MiniControlApi$buindRequest$1` phát request command **32**. MainApp
`UBTBleConfigureNetwork.sendWifiResultToMobile/sendConnectSuccess/sendErrorCodeToPhone`
phát protobuf response trên command **1032**; một số event này có msgType REQUEST (push),
không được giả định mọi thông báo 1032 là response one-shot.
Đăng ký 32→1032 đã truy ra ở mục 13 (annotation `ProtoMsgRelation` của
`BleConfigNetworkRelation`); chưa có trace runtime của lệnh Wi-Fi.

Ở MainApp, `BindOrSwitchWifiHandler.handleMsg()` lấy `request.data`, parse JSONObject, rồi
chuyển tới `UBTBleConfigureNetwork.parseResult()`. Đây là **JSON nằm trong string của protobuf**.
Các nhánh đã kiểm chứng:

- **Sửa 2026-10-25:** khóa phân biệt thao tác là `co` (BindConfigConstants.JSON_COMMAND), không
  phải `cid` (`cid` = CLIENTID, chỉ dùng cho binding). co=2 (WIFI_NAME_TRANS) và co=21
  (WIFI_INFO_TRANS_FOR_BINDING) tới receiverWifiName; co=1 (WIFI_LIST_TRANS) yêu cầu quét Wi-Fi.
- receiverWifiName đọc `s`:string SSID, `p`:string mật khẩu, `c`:string bảo mật/capabilities;
  `b`:string BSSID là optString, `v`:string là optString mặc định `"0"`.
  `v` = `dontPingNet` của SDK (mục 13.2); bảng đầy đủ giá trị ở mục 13.
- Response.data cũng là JSON, phân biệt bằng `co`; bảng đầy đủ ở mục 13.4.
- Nhánh binding có tên trường authCode, codeVerifier, userId, sch, qm; đây không phải salt/token
  của gói AES tự tạo hiện tại. Không suy ra có thể bỏ qua bước tài khoản/ủy quyền của firmware.
- Không phát hiện AES decrypt trong đường data→JSONObject→receiverWifiName đã trace. Điều đó
  không chứng minh mọi kênh hoặc mọi firmware đều không mã hóa. Không đưa mật khẩu vào frame
  thử nghiệm hay log; các payload mạng thực phải được che trước khi chia sẻ.

## 4. Trình tự, auth và các nhánh không phản hồi

1. Kết nối GATT; discover service/characteristic đúng UUID; subscribe INDICATE và chờ CCCD
   `0x2902=02 00` được xác nhận. Việc chỉ đăng ký callback không chứng minh CCCD đã sẵn sàng.
2. Gửi command **0**, bodyData là BluetoothHandShakeRequest, trong envelope/framing và
   GATT trailer mô tả trên. parseMessage() nhận command 0 và gọi onHandShake().
3. Robot trả command **1000**, bodyData BluetoothShakeResponse, responseSerial bằng
   sendSerial của request. replyHandShakePacketForKickOff/HoldOn dùng RESPONSE_COMPLETELY.
4. Thành công: kiểm tra isSuccess, lưu/che sessionId mới, đọc btInterfaceVersion/firmware;
   sau đó mới thử nghiệp vụ Wi-Fi của đúng phiên bản firmware.
5. Cấu hình Wi-Fi là giao dịch riêng có thông báo tiến độ/push, không phải cứ handshake thành
   công là robot đã nhận Wi-Fi hoặc đã truy cập Internet.

### Auth đang hiện diện trong đường BLE tham chiếu

Nguồn: `BleServer.onHandShake`, `handShake01`,
`replyHandShakePacketForKickOff`, `replyHandShakePacketForHoldOn`.

- Đây là quản lý chủ sở hữu/kết nối bằng uuid/sessionId, không phải gói JSON MD5/AES của app.
- sessionId rỗng đi vào nhánh kết nối đầu; uuid rỗng có nhánh legacy dùng địa chỉ thiết bị.
  Có uuid/sessionId thì server kiểm tra chủ hiện tại và đi qua HandShakeKickOff/HoldOn.
- Khi chấp nhận, response tạo sessionId bằng UUID.randomUUID(). Không in giá trị session thật
  trong báo cáo hoặc log chia sẻ. Không khẳng định sessionId là một phép chứng minh mật mã.
- Các nhánh từ chối KickOff/HoldOn đặt isSuccess=false, errorCode tương ứng -1/-2.
  Không tự diễn giải -1/-2 thành sai AES key hay sai mật khẩu Wi-Fi.
- Không có token/salt/AES trong schema hoặc đường handshake đã trace. Điều này không loại
  trừ auth/encryption ở kênh khác. Không tìm/thay khóa để chữa timeout.

Các trường hợp im lặng/ngắt có bằng chứng:

- Frame không khớp FB BF/độ dài/ED hoặc fragment chưa đủ: unpack/PacketData không tạo message
  để dispatch; không có đảm bảo sẽ trả error frame.
- bodyData/envelope không parse được protobuf: parseMessage bắt InvalidProtocolBufferException;
  không có response lỗi nghiệp vụ được tạo trong nhánh đó.
- checkServerState() không cho phép: onHandShake trả về trước khi gửi response.
- onDataRead0() nhận command nghiệp vụ từ client chưa là currentHolder: không dispatch và có
  nhánh cancelDevice/cancelCurrentDevice.
- Nhánh từ chối handshake có callback ngắt client; không đồng nhất tất cả nhánh với mốc 1 giây
  được nêu trong PDF cũ. Cần log runtime để xác định nhánh thực tế của robot đang dùng.
- CCCD không bật hoặc kết nối bị app khác chiếm cũng làm không nhận được indication; không
  được kết luận sai framing chỉ từ timeout.

## 5. Đối chiếu app / MainApp / PDF

PDF local: `UBtech docs/UBtech docs/Extra/Communication User Authentication and Encrypted Data
Transaction Solution.pdf` trong archive, 3 trang. Số trang dưới đây là số trang file.

| Thành phần | App hiện tại | MainApp.apk tham chiếu | PDF |
| --- | --- | --- | --- |
| Kênh/đóng frame | protocol.ts: uint32BE(1+JSON bytes)+method byte+JSON | FB BF+version+uint16BE length+protobuf+01+ED; thêm trailer từng GATT value | Trang 3: len(4)+encryption method(1)+encrypted payload cho app communication; không định nghĩa BLE wire frame này |
| Phân mảnh | manager.ts write nguyên packet, parser xử lý từng callback | devide chunk 16 + groupId/fragmentNo 4 byte; receiver reassemble | Không có đặc tả MTU/fragment |
| Handshake request | METHOD_AUTH=1; JSON VersionCode/EncryAlgorithm/UserId/salt/token | command 0; protobuf BluetoothHandShakeRequest | Trang 2 mô tả chuỗi trường phân cách dấu phẩy; BLE chỉ nói loại auth, không cấp opcode 1 hay schema protobuf |
| Thuật toán | MD5(UserId+salt), AES-ECB/Pkcs7, Base64 token; key ở PROTOCOL.AES_KEY, không ghi giá trị | Đường handshake đã trace dùng uuid/sessionId và currentHolder; không gọi AES/salt/token | Trang 1–2: shared AES 128-bit, AES(md5(identity+salt)), mutual auth; không chỉ định rõ mode/padding/MD5 raw hay hex |
| Handshake response | responseParse.ts đoán JSON success/code/status; hoặc method=1 thì OK | command 1000; isSuccess bool, errorCode int32, sessionId và firmware metadata | Trang 2: success/failure và xác thực danh tính robot; không có protobuf field numbers |
| Wi-Fi | METHOD_WIFI_CONFIG=2; JSON cmd=wifi_config, ssid, password | protobuf BindOrSwitchWifiRequest.data chứa JSON cid/s/p/c/b/v; response.data JSON, command 1032 đã thấy ở send | Không có schema cấu hình Wi-Fi |
| Mã hóa payload | Auth có AES token; packet Wi-Fi JSON không tự mã hóa | Không có AES decrypt trong đường Wi-Fi đã trace; GATT permissions không bắt buộc encryption | Trang 3 nói BLE đã mã hóa ở lớp protocol và phần encrypted payload là cho app communication; đây là mô tả, không chứng minh link hiện tại encrypted |
| Xác thực response | JSON parse hoặc bytes[4] làm method; không có buffer/correlation | Kiểm tra frame, ghép fragment, decode envelope, command/responseSerial, protobuf body | Không mô tả parser/stream/correlation |

Vị trí khóa/secret chỉ ghi bằng tên: app `src/ble/constants.ts:PROTOCOL.AES_KEY`,
`PROTOCOL.USER_ID`; thuật toán tại protocol.ts/buildAuthPacket. Không chép giá trị vào tài liệu.
PDF không phải bằng chứng cấp quyền sử dụng khóa/SDK hoặc bằng chứng giao thức BLE của firmware
hiện tại. Không lấy `len(4)` ở trang 3 để suy ra header cho BLE.

## 6. Một frame thử nghiệm handshake tối thiểu, không secret

Mục tiêu: kiểm tra duy nhất framing + envelope + dispatch command 0 của firmware hiện tại.
Đây là probe cấu trúc với BluetoothHandShakeRequest rỗng hợp lệ theo proto3; các trường đều
mặc định (deviceType=UNDEFINED, uuid/sessionId rỗng). Không phải login, không cấu hình Wi-Fi,
không mang token/salt/AES key và không chứng minh authorization cho các lệnh tiếp theo.

- header.commandId=0 (bỏ khỏi wire vì default), sendSerial=1, responseSerial=0 (default),
  versionCode=1, msgType=MSG_TYPE_REQUEST(2).
- bodyData rỗng/bỏ khỏi wire, tương đương serialized empty BluetoothHandShakeRequest.
- Envelope protobuf: `0A 06 10 01 20 01 28 02`.
- Frame logic dài 15 byte, L=14 (`00 0E`); GATT groupId=1, fragmentNo=1.
- **Gửi đúng một GATT Write Request, 19 byte:**

```text
FB BF 01 00 0E 0A 06 10 01 20 01 28 02 01 ED 00 01 00 01
```

Offline verification đã chạy bằng codec SDK: pack đúng frame logic trên;
parsePacketMsg tách lại đúng frame, groupId=1/fragmentNo=1; unpack trả một message;
parse protobuf khôi phục đúng envelope; empty handshake parse thành công.
Bốn descriptor SDK đã đối chiếu bằng FileDescriptorProto equality với APK thật. Không gọi
AlphaMiniSdk.init(), không chạy code mạng, không gửi byte tới robot trong kiểm chứng offline.
Stub android.util.Log chỉ dùng cho chương trình JVM kiểm chứng, không sửa SDK/app.

Script local đã chạy (không cần SDK và không nhận tham số secret):
`D:/Temp/ble-protocol-spec-20261025/generate_handshake_probe.py`.
Để tái tạo ngay cả khi thư mục tạm không còn, dùng đoạn stdlib tương đương sau:

```python
def varint(value):
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def uint(field, value):
    return varint(field << 3) + varint(value)


header = uint(2, 1) + uint(4, 1) + uint(5, 2)
envelope = bytes([0x0A, len(header)]) + header
length = len(envelope) + 6
frame = bytes.fromhex('FB BF 01') + length.to_bytes(2, 'big') + envelope + bytes.fromhex('01 ED')
att_value = frame + (1).to_bytes(2, 'big') + (1).to_bytes(2, 'big')
assert len(att_value) == 19
print(att_value.hex(' ').upper())
```

### Thao tác nRF Connect do người dùng thực hiện

1. Ngắt/force-stop AlphaMiniApp và app UBTECH khác; thử lúc không có client khác giữ robot,
   vì handshake có nhánh thay chủ kết nối. Không thay quyền Android, MTU hay Wi-Fi trong lượt này.
2. Mở Scanner, scan và chọn đúng serial `EAA014UBT00012017`. MAC có thể đổi sau bật lại,
   nên không hard-code MAC cũ `66:63:15:ED:40:4D`. Bấm Connect trên thiết bị vừa quét.
3. Discover service `10057e66-...`. Trên characteristic INDICATE `7e0dffa2-...`, bật indication;
   chờ log cho biết ghi CCCD thành công (`0x2902`, giá trị `02 00`). Chưa write nếu bước này lỗi.
4. Trên characteristic READ/WRITE `d2f9ff26-...`, chọn **Write Request / with response**,
   kiểu **Byte array/Hex**, nhập đúng 19 byte trên và gửi một lần. Không gửi chuỗi ASCII của hex,
   không thêm newline, không bỏ 4 byte trailer. Frame vừa MTU 23 nên không cần Request MTU.
5. Giữ kết nối, thu toàn bộ indication và log thời gian khoảng 10–15 giây, kể cả nhiều chunk.
   Chưa gửi Wi-Fi/auth frame khác và chưa đổi thêm biến trong cùng lượt.

### Kết quả mong đợi và giới hạn diễn giải

- Nếu đúng họ giao thức và handler được phép hoạt động, indication sẽ ghép thành frame
  FB BF/version/length/.../01 ED; commandId protobuf **1000**, responseSerial **1**;
  bodyData decode được thành BluetoothShakeResponse. Không kỳ vọng nguyên frame có một
  hex cố định: locale, firmware, sessionId và groupId được tạo động.
- Chấp nhận: isSuccess=true và thường có sessionId/version metadata. Từ chối vẫn là bằng
  chứng parser/handler hoạt động nếu nhận response hợp lệ isSuccess=false, errorCode -1/-2.
- Response có thể dài hơn 20 byte: chỉ chunk đầu bắt đầu FB BF; ghép data của các chunk cùng
  groupId, fragmentNo tăng dần, bỏ trailer trước khi đọc protobuf. Không nhầm command 1000
  với groupId ở trailer.
- Không có indication chưa đủ kết luận sai protocol: còn CCCD, state server/current holder,
  phiên bản firmware, lỗi GATT và nhánh empty/default handshake. Không khẳng định probe sẽ
  thành công trên robot hiện tại trước khi có trace.
- Che sessionId/uuid thực, dữ liệu tài khoản và thông tin Wi-Fi trước khi chia sẻ log. Probe
  gửi đi không chứa các giá trị này; tài liệu không tạo frame Wi-Fi có mật khẩu rõ.

## 7. Phạm vi thay đổi nếu probe được firmware xác nhận

Ước lượng 5 phần logic, khoảng 6–8 file hiện có và thêm module/schema protobuf:

1. Codec/packetizer: frame FB BF, length, fixed byte/end, groupId/fragmentNo và buffer reassembly
   (module mới, tích hợp vào protocol.ts/responseParse.ts).
2. Payload/command: handshake protobuf 0/1000, sau đó Wi-Fi protobuf+JSON đúng firmware;
   cập nhật constants.ts và protocol.ts, không tự giữ gói AES hiện tại cho nhánh này.
3. State machine manager.ts: ghi từng fragment theo thứ tự, chờ indication/response tương ứng,
   kiểm tra command+responseSerial và trạng thái nghiệp vụ. Không đổi timeout/MTU đồng thời
   chỉ để làm test pass; CCCD readiness cần bằng chứng riêng.
4. Diagnostics/tests: che sessionId/authCode/codeVerifier và dữ liệu Wi-Fi trong diagnostics.ts;
   fixture request/response/chunk, lỗi frame/trailer/correlation trong __tests__/ble-protocol.test.ts.
5. Wi-Fi UI/hook nếu firmware yêu cầu capabilities/BSSID/chọn từ robot scan list; chỉ xác định
   cụ thể sau khi handshake thành công và trích đủ các cid. Chưa có bằng chứng cần đổi thư viện
   BLE hoặc server LAN để chữa framing BLE.

Chưa triển khai các phần này. Bản sửa prefix 9de6ec6 đã merge riêng; nhánh docs/ble-protocol
chỉ chứa tài liệu. Dừng sau chuẩn bị probe, chờ người dùng tự thử/review.

## 8. Bằng chứng và cách tái kiểm tra

- `aapt dump badging <MainApp.apk>`; `aapt dump xmltree <MainApp.apk> AndroidManifest.xml`.
- `dexdump -d classes.dex`, `dexdump -d classes2.dex` từ APK có hash ở mục 1.
- Lớp/method then chốt: UBTGattService.<clinit>/<init>; UBTGattServer$4.onCharacteristicWriteRequest;
  MiniBleProto.pack/unpack/parsePacketMsg/devide; BleServer$BleDataReceiver.parseMessage;
  BleServer.onHandShake/replyHandShakePacketForKickOff/replyHandShakePacketForHoldOn/onDataRead0;
  BindOrSwitchWifiHandler.handleMsg; UBTBleConfigureNetwork.parseResult/receiverWifiName/sendWifiResultToMobile.
- Schema thật, trích đoạn đã che literal và probe verification ở
  `D:/Temp/ble-protocol-spec-20261025/`: actual-robot-descriptors.json,
  probe-offline-verification.txt, VerifyProbe.java, generate_handshake_probe.py.
- Trace robot trước đó ở `D:/Temp/ble-provision-evidence-20261024/`:
  round1-provision-events.redacted.json (auth request header 000000a401; timeout, không response).
- PDF ở archive là nguồn mô tả thiết kế so sánh; không dùng thay bytecode hoặc trace runtime.
- Archive và tài liệu vendor là dữ liệu tham khảo; không đưa APK/AAR, khóa hoặc dump chứa literal
  vendor vào Git trong commit tài liệu này.
## 9. Probe PC trên robot thật — 2026-10-25 (UTC+07:00)

Không có lượt nRF mới: người dùng xác nhận chưa thử nRF và cho phép probe từ PC.
PC có MediaTek Bluetooth Adapter / Microsoft Bluetooth LE Enumerator trạng thái OK.
Môi trường riêng `D:/Temp/ble-probe` dùng Python 3.12, bleak 3.0.2; không thay requirements
hoặc venv dự án. Qua adb đã force-stop `com.alphaminiapp` và `no.nordicsemi.android.mcp`.

Mỗi lượt quét 15 giây, chọn duy nhất tên bắt đầu Mini_ không phân biệt hoa/thường,
connect, bật indication (characteristic chỉ có property indicate), write-with-response đúng
19 byte ở mục 6, quan sát 10 giây rồi chủ động disconnect. Nghỉ 10 giây trước lượt quét 2.
Không thay MTU, không gửi Wi-Fi, không đưa credential vào request.

| Lượt | Quét / RSSI | Write bắt đầu → ACK | Indication đầu → cuối | Kết thúc |
|---|---|---|---|---|
| 1 | 00:59:58.896–01:00:14.217; raw 6, matched 1; -46 dBm | 01:00:17.342 → .371 | 01:00:17.431 → .550; 5 fragment | 01:00:27.381 vẫn connected; ngắt chủ động |
| 2 | 01:00:37.507–52.555; raw 7, matched 1; -47 dBm | 01:00:55.339 → .369 | 01:00:55.400 → .535; 5 fragment | 01:01:05.381 vẫn connected; ngắt chủ động |

Cùng robot `Mini_EAA014UBT00012017`, địa chỉ tại hai lượt `44:A8:35:62:53:2A`.
Mỗi lượt nhận các ATT value dài 20, 20, 20, 20, 17 byte; bỏ trailer 4 byte mỗi fragment,
ghép được core frame 77 byte. Group ID lượt 1 = 29179, lượt 2 = 9001; sequence 1–5.
SDK `MiniBleProto` parsePacketMsg/unpack và lớp protobuf BluetoothShakeResponse giải mã
được đúng một message mỗi lượt. Đây là trace thật, khác roundtrip giả lập ở mục 6.

Kết quả header giống nhau ở hai lượt:

- commandId = 1000; sendSerial = 0; responseSerial = 1.
- versionCode = 0 (giá trị thực tế; không ép thành 1 theo suy luận từ builder tham chiếu).
- msgType = MSG_TYPE_RESPONSE_COMPLETE (0); header.resultCode = 0.

Toàn bộ trường BluetoothShakeResponse, giống nhau trừ sessionId mới theo từng lượt:

- isSuccess = true; resultCode = false (bool mặc định, không phải mã lỗi).
- sysLan = "US"; sysCountry = "".
- robotSoftVersionName = "v2.2.5.917"; btInterfaceVersion = 2.
- androidFirmwareVersion = ""; errorCode = 0; versionInfo = "1".
- sessionId: có giá trị, 36 ký tự; che vì là credential phiên. Không commit giá trị thật.

Kết luận có bằng chứng: firmware hiện tại chấp nhận framing/fragment trailer của probe
19 byte và trả handshake thành công hai lần. Chưa chứng minh command/cid Wi-Fi, account
binding hoặc BLE→LAN. btInterfaceVersion=2 không tự chứng minh có thể bỏ trailer ở request sau.
Không có ngắt kết nối ngoài dự kiến trong cửa sổ quan sát.

Evidence local (không commit raw vì response chứa sessionId):
`D:/Temp/ble-probe/events.jsonl` (hex + timestamp millisecond), `run1.hex`, `run2.hex`,
`run1-decoded.redacted.txt`, `run2-decoded.redacted.txt`, `probe.py`, `DecodeProbe.java`, `decode.py`.
Java helper dùng chính codec/classes SDK và protobuf jar offline, kiểm tra group/sequence,
length rồi parse envelope và body. Không nhúng AAR vào dự án. Các dòng hex dưới đây được che
sessionId bằng XX; không dùng làm golden frame nguyên trạng có thể decode.

## 10. AppId/AppKey và kiểm tra offline: phạm vi kết luận

Đường code trong MainApp.apk tham chiếu:

1. UBTGattServer$4.onCharacteristicWriteRequest → BleServer$BleDataReceiver.parseMessage:
   unpack, lấy commandId=0, parse BluetoothHandShakeRequest.
2. BleServer.onHandShake tại DEX offset 1e2e90 gọi checkServerState; hàm này đọc started
   AtomicBoolean. Request schema chỉ có 7 trường đã liệt kê ở mục 3, không có AppId/AppKey/chữ ký.
3. onHandShake kiểm tra uuid/sessionId và holder qua HandShakeKickOff/HandShakeHoldOn;
   empty uuid đi nhánh lấy địa chỉ Bluetooth. handShake01 và replyHandShakePacketForKickOff/
   HoldOn tạo BluetoothShakeResponse, trả command 1000 với responseSerial từ request.
4. Các nhánh này so sánh holder/session, tạo session UUID, không gọi Cipher, MessageDigest,
   Signature hay kiểm tra AppId/AppKey; postHandShakeStatus chỉ đăng callback sau phản hồi.

Bằng chứng kết hợp schema + luồng điều khiển + probe thật: command 0 → 1000 này không cần
AppId/AppKey/chữ ký và không có bước kiểm tra offline các credential ấy trong đường đã rà soát.
Probe gửi body rỗng vẫn nhận isSuccess=true hai lần. Điều này không đồng nghĩa bỏ kiểm tra
session/holder, và không suy rộng sang cloud/account binding hoặc mọi firmware.
SDK client yêu cầu AppId/AppKey khi khởi tạo là lớp khác. Chưa có blocker AppKey cho handshake
đã thử; nếu Wi-Fi/binding sau này yêu cầu credential UBTECH thì dừng để chọn credential/license
hợp lệ, dùng app chính hãng cấu hình Wi-Fi rồi LAN, hoặc hoãn nhánh binding. Không sao chép key.
APK tham chiếu V2.2.4#1024 khác phiên bản robot báo v2.2.5.917; chỉ các điểm probe xác nhận mới
được coi là đã kiểm chứng trên firmware này.

## 11. Kế hoạch triển khai chờ duyệt — chưa sửa app

Tự viết codec/protobuf TypeScript theo schema đã kiểm tra; không nhúng AAR, không đưa key SDK
vào app. Khi chuyển runtime sẽ thay hẳn giao thức AES/JSON cũ, không chạy hai giao thức song song
và không fallback sang auth cũ. Giữ các thông số scan/timeout/MTU ngoài phạm vi thử nghiệm này.

1. Commit golden vectors và test codec thuần: frame SDK offline có dữ liệu giả, fragment/trailer,
   envelope/header/body, partial/multiple frames, sai length, thiếu/lặp/đảo fragment, sai serial.
   Dùng trace thật kiểm tra cấu trúc/giá trị không nhạy cảm; fixture công khai thay sessionId bằng
   giá trị giả rồi encode lại bằng SDK, đánh dấu synthetic, không gọi đó là nguyên bản capture.
2. Commit codec/protobuf TS và chuyển runtime handshake một lần: protocol.ts, responseParse.ts,
   constants.ts, manager.ts; bỏ auth AES/JSON/method-1 fallback. Đường chưa có Wi-Fi mới phải dừng
   rõ sau handshake, không gọi Wi-Fi cũ và không báo provisioning thành công. Test fail trước/pass
   sau, verify, build APK test; robot xác nhận command 1000, responseSerial, isSuccess và session.
3. Commit Wi-Fi sau khi rà đủ request command/cid và semantics của firmware: protobuf + JSON,
   mã lỗi/progress, security/capabilities/BSSID nếu cần. Không suy ra success chỉ vì write ACK.
   Test golden request/response và negative cases; thử trên robot sau handshake đã ổn định,
   người dùng tự nhập mật khẩu. Chỉ một thay đổi giao thức mỗi vòng, không đổi timeout để che lỗi.
4. Commit tích hợp BLE→LAN và diagnostics/tests: che sessionId/password/authCode/codeVerifier,
   kiểm tra trạng thái thành công thật và /robot/connect + /robot/state; verify, assembleRelease,
   thử độc lập không Metro. Không sửa server nếu chưa có bằng chứng cần thiết.

Mỗi commit chạy verify; mỗi mốc phần cứng lưu timestamp, TX/RX đã che và kết quả robot.
Dừng nếu phát sinh yêu cầu AppKey/license hoặc schema chưa đủ rõ; không triển khai binding theo đoán.
Phạm vi dự kiến 5 phần logic / khoảng 6–8 file như mục 7, cộng codec và test; số file cụ thể chốt
sau review. Kế hoạch này chưa được phê duyệt triển khai, không merge nhánh tài liệu ở bước này.

## 12. ATT indication evidence (XX = redacted session byte)


Run 1:

```text
2026-10-25T01:00:17.431+07:00 FB BF 01 00 4C 0A 05 08 E8 07 18 01 12 3D 08 01 71 FB 00 01
2026-10-25T01:00:17.461+07:00 1A 02 55 53 2A 0A 76 32 2E 32 2E 35 2E 39 31 37 71 FB 00 02
2026-10-25T01:00:17.492+07:00 30 02 4A 24 XX XX XX XX XX XX XX XX XX XX XX XX 71 FB 00 03
2026-10-25T01:00:17.520+07:00 XX XX XX XX XX XX XX XX XX XX XX XX XX XX XX XX 71 FB 00 04
2026-10-25T01:00:17.550+07:00 XX XX XX XX XX XX XX XX 52 01 31 01 ED 71 FB 00 05
```


Run 2:

```text
2026-10-25T01:00:55.400+07:00 FB BF 01 00 4C 0A 05 08 E8 07 18 01 12 3D 08 01 23 29 00 01
2026-10-25T01:00:55.430+07:00 1A 02 55 53 2A 0A 76 32 2E 32 2E 35 2E 39 31 37 23 29 00 02
2026-10-25T01:00:55.459+07:00 30 02 4A 24 XX XX XX XX XX XX XX XX XX XX XX XX 23 29 00 03
2026-10-25T01:00:55.504+07:00 XX XX XX XX XX XX XX XX XX XX XX XX XX XX XX XX 23 29 00 04
2026-10-25T01:00:55.535+07:00 XX XX XX XX XX XX XX XX 52 01 31 01 ED 23 29 00 05
```

## 13. Lệnh cấu hình Wi-Fi — đặc tả offline (2026-10-25)

Nguồn: MainApp.apk (hash mục 1) dexdump `classes2.dex` (`-d` và `-a` cho annotation) và SDK
client `alpha-mini-oversea-edu-sdk-0.0.9` (javap). Chưa thử trên robot; mọi điểm dưới đây là
bằng chứng bytecode, firmware thật (v2.2.5.917) có thể khác V2.2.4 tham chiếu.

### 13.1 Định tuyến và cổng chặn trên robot

- `BleConfigNetworkRelation` (extends IProtoMsgRelation) có annotation
  `ProtoMsgRelation{msgClass=BindOrSwitchWifiRequest, msgHandleClass=BindOrSwitchWifiHandler,
  requestCmdId=32, responseCmdId=1032}`. `CmdId.BL_BIND_OR_SWITCH_WIFI_REQUEST=32`,
  `..._RESPONSE=1032`.
- Đường đi: GATT write → `BleServer$BleDataReceiver$1.run` (ghép mảnh) → `parseMessage`
  (command≠0) → `BleServer.onDataRead0` → `ChannelServer$6.run` →
  `BleMessageDispatcherEngine.dispatchProtoMsg` → `BindOrSwitchWifiHandler.handleMsg`.
- Cổng duy nhất: `onDataRead0` chỉ dispatch nếu client BLE là `currentHolder` (đã handshake
  thành công); ngược lại log "ble device no HandShake or has been kick off" và ngắt client.
- `ChannelServer$6.run` bỏ request có `sendSerial` trùng request trước của cùng uuid
  ("duplicate request") → app phải tăng sendSerial cho mỗi request.
- dispatchProtoMsg chỉ đọc commandId/sendSerial/responseSerial/versionCode; **không đọc msgType**.
- Ghép mảnh request (`PacketData.putBytes`): mảnh đầu được lưu; mảnh sau cùng groupId được nối
  rồi thử unpack cả buffer; groupId khác → xóa buffer và bắt đầu lại; fragmentNo trùng mảnh
  trước → bỏ qua. Không có ACK lỗi khi ghép thất bại (im lặng).

**AppKey/chữ ký/tài khoản: KHÔNG cần cho co=4/co=2/co=12.** Không có Cipher/MessageDigest/
Signature/AppId trên đường trên; handler chỉ parse JSON. Nhánh binding (co=21, co=3 với
`cid`/`authCode`/`codeVerifier`/`userId`, co=11 Alexa) dùng dữ liệu tài khoản — app không dùng.

### 13.2 Request: command 32, `BindOrSwitchWifiRequest{data, versionCode}`

- Header theo builder SDK `ProtoBufferDispose.a(cmd, version, sendSerial, responseSerial, body)`:
  commandId=32, sendSerial, responseSerial=0, versionCode=1; **msgType không đặt** (mặc định 0).
- Body: `data` = chuỗi JSON; `versionCode=168` (SDK `BleConfigDataSource$e`). Robot: nếu
  versionCode≠168 và co=4 thì phát thêm TTS; ngoài ra không dùng.
- JSON do SDK sinh (Gson, bỏ field null; thứ tự khóa s, c, p, b, v, co):

| co | Ý nghĩa (BindConfigConstants) | Trường | Robot làm gì |
| --- | --- | --- | --- |
| 4 | CONNECT_SUCCESS — app báo đã nối BLE | — | Nếu IM network skill đang chạy → push 104 với cd `"2"`; ngược lại bật BleNetworkSkill, quét Wi-Fi, tạo luồng gửi danh sách, push `{"co":104,"cd":0}` |
| 2 | WIFI_NAME_TRANS — gửi Wi-Fi (không binding) | `s` SSID (bắt buộc), `p` mật khẩu (bắt buộc, có thể rỗng), `c` bảo mật (bắt buộc), `b` BSSID (tùy chọn), `v` dontPingNet (tùy chọn, mặc định "0") | Dừng hẹn giờ, kết nối Wi-Fi (mục 13.3) |
| 1 | WIFI_LIST_TRANS — quét lại | — | Xóa danh sách; gửi danh sách qua luồng của co=4 |
| 10 | STOP_SEND_WIFI_LIST | — | Ngừng gửi danh sách, push `{"co":110}` |
| 12 | QUIT_BLE_NETWORK_SKILL | — | Dừng skill, luồng gửi; chỉ tắt card mạng khi đang ở chế độ 4G |
| 21, 3, 8, 9, 11 | binding / clientId / 4G / Alexa | tài khoản | Không dùng |

Thiếu `s`, `p` hoặc `c` → JSONException bị bắt trong parseResult, **robot im lặng**.
SDK gọi `b.a(cap, ssid, pwd, bssid, dontPingNet)`; `dontPingNet` mặc định "0" trong SDK.

Bảo mật (`BleNetworkWifiManager.createWifiInfo`): mật khẩu rỗng → mạng mở; `c` chứa "WEP" →
WEP; mọi giá trị khác (kể cả "WPA2", "WPA", "N") → WPA-PSK với preSharedKey. `b` được gán thẳng
vào `WifiConfiguration.BSSID` (rỗng nếu app không gửi) — rủi ro chưa kiểm chứng trên firmware này.
Danh sách quét của robot ghi `c` là "WEP"/"WPA2"/"WPA"/"N".

### 13.3 Trình tự kết nối trên robot

1. `receiverWifiName` → `connectedBegin`: nếu BSSID hiện tại = `b` thì coi như đã nối →
   kiểm tra mạng ngay; nếu không: hẹn giờ **60 000 ms** (`startConnectWifiTimer`), đặt trạng
   thái CONNECTING, chạy `ConnectRunnable` (addNetwork/enableNetwork/reconnect).
2. `connect()` trả false → push lỗi ec=12.
3. Broadcast: lỗi xác thực → `bandingEnd` → TTS sai mật khẩu, push ec=1; lỗi khác
   `connectWifiError` → ec=0; từ CONNECTING sang DISCONNECTED → quên mạng, ec=13; hết 60 s → ec=4.
4. CONNECTED đúng SSID → `doWifiCheck`: nếu `v`="1" push `{"co":102}` ngay; nếu không, kiểm tra
   Internet (CheckWifiLoginTask/ping): cần đăng nhập web → quên mạng, ec=11; không ra Internet →
   quên mạng, ec=12; thành công → `{"co":102}` và TTS báo nối mạng thành công.
5. Không có mã riêng cho "không tìm thấy SSID": thực tế rơi vào ec=13/ec=4/ec=0.

### 13.4 Thông báo robot → app: command 1032, `BindOrSwitchWifiResponse{data}`

Gửi bằng `ChannelServer.sendMessageByBle(1032, version 1, responseSerial 0, …, MessageType.REQUEST)`
→ push, **không** mang responseSerial của request; app phải lọc theo `co` trong `data`.

| `data` | Ý nghĩa |
| --- | --- |
| `{"co":104,"cd":0}` | Đáp co=4: sẵn sàng cấu hình. `cd` "1"/"2" (chuỗi) = robot đang được thiết bị khác cấu hình |
| `{"co":101,"p":"[…]"}` | Danh sách Wi-Fi; `p` là **chuỗi** JSON mảng `{l:RSSI,s:SSID,b:BSSID,c:"WEP"/"WPA2"/"WPA"/"N",o:đã từng nối,u:đang nối,g:false}` |
| `{"co":102}` | Robot đã nối Wi-Fi (và qua kiểm tra Internet nếu v≠"1") |
| `{"co":-1,"ec":N}` | Lỗi (bảng dưới) |
| `{"co":105,…}`, `{"co":108,…}`, 103/109/110/111 | Trạng thái mạng/4G/binding/ngừng danh sách — không dùng cho luồng này |

| ec | Hằng | Nghĩa |
| --- | --- | --- |
| 0 | CONNENT_WIFI_FIALED_ERROR_CODE | Kết nối thất bại (lỗi supplicant khác) |
| 1 | PASSWORD_VALIDATA_ERROR_CODE | Sai mật khẩu |
| 2 | PING_ERROR_CODE | Ping lỗi (không thấy nơi phát trong bản V2.2.4) |
| 3, 6 | TVS_LOGIN_ERROR_CODE, TVS_ERROR_CODE | Dịch vụ giọng nói |
| 4 | CONNECT_TIME_OUT_ERROR_CODE | Hết 60 s chưa nối được |
| 5 | ALEARDY_CONNECT_ERROR_CODE | Đã kết nối |
| 7, 8 | ERROR_CODE_4G, ERROR_CODE_4G_NO_SIM | 4G |
| 11 | WIFI_NEED_AUTH_ERROR_CODE | Wi-Fi cần đăng nhập web (captive portal) |
| 12 | WIFI_CANT_ACCESS_INTERNET | Không ra Internet, hoặc addNetwork/enable thất bại |
| 13 | WIFI_CANT_BE_CONNECTED | Không nối được (rớt từ CONNECTING) |
| 14 | OTHER_DEVICE_CONNECT | Thiết bị khác đang kết nối |

### 13.5 Lệnh quét Wi-Fi trên robot — chỉ ghi nhận

Có. Sau co=4 (hoặc co=1 để quét lại), luồng `WifiSender` lấy kết quả quét, lọc (bỏ SSID rỗng,
IBSS, trùng SSID giữ RSSI mạnh; 5 GHz bị lọc ở một số bản), chia nhóm **2 mạng mỗi thông báo**
và push `{"co":101,"p":…}` khoảng mỗi 10 s cho tới co=10 (robot đáp co=110) hoặc co=12.
Mỗi mục có BSSID và `c` → dùng được cho UX "chọn mạng từ danh sách robot" và để gửi `b`/`c` chính
xác. App lượt này **không** dùng danh sách (chỉ đếm, không log SSID lân cận).

### 13.6 Trình tự app chọn cho lần thử đầu (chưa kiểm chứng trên robot)

1. Handshake command 0 (frame 19 byte đã chứng minh, sendSerial=1) → chờ 1000, isSuccess.
2. command 32 `{"co":4}` sendSerial=2 → chờ 1032 co=104 (cd≠0 → báo thiết bị khác đang cấu hình).
3. command 32 `{"s","c","p","v":"0","co":2}` sendSerial=3; `c`="WPA2" nếu có mật khẩu, "N" nếu
   không; không gửi `b`. Chờ 1032 co=102 hoặc co=-1; bỏ qua co=101. App chờ 90 s
   (robot tự hẹn 60 s + kiểm tra Internet), thay cho 30 s cũ vốn ngắn hơn hẹn giờ của robot.
4. command 32 `{"co":12}` sendSerial=4 (best effort, không chờ) rồi ngắt BLE.
Biến dự phòng nếu robot báo lỗi: gửi `b`/`c` từ danh sách co=101; `v`="1" nếu mạng LAN không
có Internet (ec=11/12). Chỉ đổi từng biến một, có log.

Golden offline (SDK, Wi-Fi giả) và công cụ sinh: `GenGolden.java` chạy SDK classes.jar +
protobuf-java 3.10.0 + gson 2.8.6 + org.json + kotlin-stdlib, stub `android.util.Log`, không
nhúng gì vào repo. Kết quả lưu ở `AlphaMiniApp/__tests__/fixtures/ble-golden-sdk.json`.
