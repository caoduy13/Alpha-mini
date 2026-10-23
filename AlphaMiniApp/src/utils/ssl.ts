/**
 * HTTPS self-signed trên LAN (Alpha Mini Server):
 * - Android: `res/xml/network_security_config.xml` tin user CA + cleartext fallback.
 * - Cài chứng chỉ server vào “Credential storage” trên điện thoại nếu vẫn SSL handshake fail.
 * - Hoặc dùng `http://<IP>:8000` khi SERVER_SSL_ENABLED=false để dev nhanh.
 */
export const SSL_DEV_NOTES =
  'HTTPS LAN: cài cert vào máy hoặc dùng HTTP trong Settings khi server tắt SSL.';
