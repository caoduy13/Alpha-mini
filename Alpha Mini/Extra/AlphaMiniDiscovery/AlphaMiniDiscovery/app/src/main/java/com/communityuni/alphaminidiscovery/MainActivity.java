package com.communityuni.alphaminidiscovery;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.View;
import android.view.animation.AccelerateDecelerateInterpolator;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.communityuni.alphaminidiscovery.databinding.ActivityMainBinding;
import com.communityuni.alphaminidiscovery.model.ChatMessage;
import com.communityuni.alphaminidiscovery.model.RobotStatus;
import com.communityuni.alphaminidiscovery.network.RobotController;
import com.communityuni.alphaminidiscovery.utils.PrefsManager;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class MainActivity extends AppCompatActivity {

    private ActivityMainBinding vb;
    private PrefsManager prefs;
    private RobotController controller;

    private final List<ChatMessage> messages = new ArrayList<>();
    private ChatAdapter chatAdapter;

    private boolean sessionActive = false;
    private long connectedSinceMs = 0L;
    private String lastIp = "";

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        vb = ActivityMainBinding.inflate(getLayoutInflater());
        setContentView(vb.getRoot());

        prefs = new PrefsManager(this);
        controller = new RobotController();

        setupChat();
        wireUi();

        // Tự load IP đã lưu
        String ip = prefs.getRobotIp();
        if (ip != null && ip.trim().length() > 0) {
            connectAndRefresh(ip.trim(), false);
        } else {
            setOnline(false);
            setEmotion("😊", getString(R.string.emotion_unknown), false);
        }
    }

    private void wireUi() {
        vb.btnOpenSettings.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                openSettings();
            }
        });
        vb.btnQuickSettings.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                openSettings();
            }
        });

        vb.btnQuickReconnect.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String ip = prefs.getRobotIp();
                if (ip == null || ip.trim().isEmpty()) {
                    Toast.makeText(MainActivity.this, R.string.toast_need_ip, Toast.LENGTH_SHORT).show();
                    return;
                }
                connectAndRefresh(ip.trim(), true);
            }
        });

        vb.btnQuickStatus.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String ip = prefs.getRobotIp();
                if (ip == null || ip.trim().isEmpty()) {
                    Toast.makeText(MainActivity.this, R.string.toast_need_ip, Toast.LENGTH_SHORT).show();
                    return;
                }
                fetchStatus(ip.trim(), true);
            }
        });

        vb.btnQuickMute.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                boolean next = !prefs.isMuted();
                prefs.setMuted(next);
                Toast.makeText(MainActivity.this, next ? R.string.toast_muted : R.string.toast_unmuted, Toast.LENGTH_SHORT).show();
            }
        });

        vb.btnStart.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String ip = prefs.getRobotIp();
                if (ip == null || ip.trim().isEmpty()) {
                    Toast.makeText(MainActivity.this, R.string.toast_need_ip, Toast.LENGTH_SHORT).show();
                    return;
                }
                sendCommand(ip.trim(), "start_chat", true);
            }
        });

        vb.btnStop.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String ip = prefs.getRobotIp();
                if (ip == null || ip.trim().isEmpty()) {
                    Toast.makeText(MainActivity.this, R.string.toast_need_ip, Toast.LENGTH_SHORT).show();
                    return;
                }
                sendCommand(ip.trim(), "stop_chat", true);
            }
        });

        vb.btnSend.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String ip = prefs.getRobotIp();
                if (ip == null || ip.trim().isEmpty()) {
                    Toast.makeText(MainActivity.this, R.string.toast_need_ip, Toast.LENGTH_SHORT).show();
                    return;
                }
                String cmd = vb.edtCommand.getText() == null ? "" : vb.edtCommand.getText().toString().trim();
                if (cmd.isEmpty()) return;
                vb.edtCommand.setText("");
                sendSay(ip.trim(), cmd);
            }
        });

        vb.cardConversation.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                // UX: tap card để mở settings nhanh (dễ chỉnh IP)
                openSettings();
            }
        });
    }

    private void openSettings() {
        Intent intent = new Intent(this, SettingsActivity.class);
        startActivity(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Nếu user vừa đổi IP trong Settings
        String ip = prefs.getRobotIp();
        if (ip != null) ip = ip.trim();
        if (ip == null) ip = "";
        if (!ip.equals(lastIp) && ip.length() > 0) {
            connectAndRefresh(ip, false);
        }
    }

    private void setupChat() {
        vb.rvChat.setLayoutManager(new LinearLayoutManager(this, RecyclerView.VERTICAL, false));
        chatAdapter = new ChatAdapter(messages);
        vb.rvChat.setAdapter(chatAdapter);
    }

    private void connectAndRefresh(final String ip, final boolean showToast) {
        lastIp = ip;
        if (showToast) Toast.makeText(this, R.string.toast_connecting, Toast.LENGTH_SHORT).show();
        setEmotion("🤔", getString(R.string.emotion_thinking), prefs.isShowEmotionAnim());
        fetchStatus(ip, showToast);
    }

    private void fetchStatus(final String ip, final boolean showToast) {
        controller.sendCommand(ip, "status", new RobotController.Listener() {
            @Override
            public void onSuccess(final RobotStatus status) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        prefs.setRobotIp(ip);
                        vb.txtIp.setText(ip);
                        setOnline(true);
                        sessionActive = status != null && status.session_active;
                        vb.btnStop.setEnabled(sessionActive);
                        if (connectedSinceMs == 0L) connectedSinceMs = SystemClock.elapsedRealtime();
                        updateUptime();

                        setEmotion(sessionActive ? "😊" : "😊",
                                sessionActive ? getString(R.string.emotion_happy) : getString(R.string.emotion_happy),
                                prefs.isShowEmotionAnim());

                        if (showToast) Toast.makeText(MainActivity.this, R.string.toast_connected, Toast.LENGTH_SHORT).show();
                    }
                });
            }

            @Override
            public void onError(final String message) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        setOnline(false);
                        vb.btnStop.setEnabled(false);
                        connectedSinceMs = 0L;
                        vb.txtUptime.setText(R.string.status_uptime_unknown);
                        setEmotion("😔", getString(R.string.emotion_unknown), prefs.isShowEmotionAnim());
                        if (showToast) Toast.makeText(MainActivity.this, R.string.toast_connect_failed, Toast.LENGTH_LONG).show();
                    }
                });
            }
        });
    }

    private void sendCommand(final String ip, final String action, final boolean addChat) {
        if (addChat) {
            addMessage(new ChatMessage(true, action, System.currentTimeMillis()));
        }
        controller.sendCommand(ip, action, new RobotController.Listener() {
            @Override
            public void onSuccess(final RobotStatus status) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        setOnline(true);
                        sessionActive = status != null && status.session_active;
                        vb.btnStop.setEnabled(sessionActive);
                        if (connectedSinceMs == 0L) connectedSinceMs = SystemClock.elapsedRealtime();
                        updateUptime();

                        // Robot trả về session_active: mình map thành emotion cho UI
                        setEmotion(sessionActive ? "😊" : "😊",
                                sessionActive ? getString(R.string.emotion_happy) : getString(R.string.emotion_happy),
                                prefs.isShowEmotionAnim());

                        // Hiển thị phản hồi dạng bubble
                        String reply = status == null ? "ok" : ("ok (session_active=" + status.session_active + ")");
                        addMessage(new ChatMessage(false, reply, System.currentTimeMillis()));
                    }
                });
            }

            @Override
            public void onError(final String message) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        // Với lệnh điều khiển (start/stop), nếu lỗi mạng thì KHÔNG vội chuyển Offline,
                        // chỉ hiện bubble lỗi. Trạng thái Online/Offline nên được quyết định bởi lệnh status.
                        addMessage(new ChatMessage(false, "error: " + message, System.currentTimeMillis()));
                    }
                });
            }
        });
    }

    private void sendSay(final String ip, final String text) {
        addMessage(new ChatMessage(true, text, System.currentTimeMillis()));
        controller.sendCommand(ip, "say", text, new RobotController.Listener() {
            @Override
            public void onSuccess(final RobotStatus status) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        setOnline(true);
                        // say không đổi session_active; vẫn cập nhật nếu có.
                        sessionActive = status != null && status.session_active;
                        vb.btnStop.setEnabled(sessionActive);
                        String reply = status == null ? "ok" : ("ok (session_active=" + status.session_active + ")");
                        addMessage(new ChatMessage(false, reply, System.currentTimeMillis()));
                    }
                });
            }

            @Override
            public void onError(final String message) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        // Gửi chat/lệnh mà lỗi thì giữ trạng thái Online, tránh UX "Online → Offline" liên tục.
                        addMessage(new ChatMessage(false, "error: " + message, System.currentTimeMillis()));
                    }
                });
            }
        });
    }

    private void addMessage(ChatMessage msg) {
        messages.add(msg);
        if (messages.size() == 1) {
            vb.txtConversationPlaceholder.setVisibility(View.GONE);
            vb.rvChat.setVisibility(View.VISIBLE);
        }
        chatAdapter.notifyItemInserted(messages.size() - 1);
        vb.rvChat.scrollToPosition(messages.size() - 1);
    }

    private void setOnline(boolean online) {
        if (online) {
            vb.txtStatusBadge.setText(R.string.status_online);
            vb.txtStatusBadge.setTextColor(getResources().getColor(R.color.status_online));
            vb.avatarRing.setAlpha(1f);
            vb.txtStatusBadge.animate().cancel();
            vb.txtStatusBadge.setAlpha(1f);
        } else {
            vb.txtStatusBadge.setText(R.string.status_offline);
            vb.txtStatusBadge.setTextColor(getResources().getColor(R.color.status_offline));
            // Blink khi Offline
            vb.txtStatusBadge.animate().alpha(0.25f).setDuration(500).setInterpolator(new AccelerateDecelerateInterpolator()).withEndAction(new Runnable() {
                @Override
                public void run() {
                    vb.txtStatusBadge.animate().alpha(1f).setDuration(500).start();
                }
            }).start();
        }
    }

    private void updateUptime() {
        if (connectedSinceMs <= 0L) return;
        long secs = (SystemClock.elapsedRealtime() - connectedSinceMs) / 1000L;
        long mins = secs / 60L;
        long hours = mins / 60L;
        long remMins = mins % 60L;
        String text = hours > 0 ? (hours + "h " + remMins + "m") : (mins + "m");
        vb.txtUptime.setText(text);
    }

    private void setEmotion(final String emoji, final String label, boolean animate) {
        if (!animate) {
            vb.txtEmoji.setText(emoji);
            vb.txtEmotion.setText(label);
            return;
        }
        vb.txtEmoji.animate().scaleX(0.9f).scaleY(0.9f).setDuration(120).withEndAction(new Runnable() {
            @Override
            public void run() {
                vb.txtEmoji.setText(emoji);
                vb.txtEmotion.setText(label);
                vb.txtEmoji.animate().scaleX(1.05f).scaleY(1.05f).setDuration(160).withEndAction(new Runnable() {
                    @Override
                    public void run() {
                        vb.txtEmoji.animate().scaleX(1f).scaleY(1f).setDuration(140).start();
                    }
                }).start();
            }
        }).start();
    }

    /**
     * Adapter chat bubble: trượt vào từ trái/phải khi có tin mới.
     */
    static class ChatAdapter extends RecyclerView.Adapter<ChatViewHolder> {
        private final List<ChatMessage> items;
        private final SimpleDateFormat fmt = new SimpleDateFormat("HH:mm:ss", Locale.getDefault());

        ChatAdapter(List<ChatMessage> items) {
            this.items = items;
        }

        @Override
        public ChatViewHolder onCreateViewHolder(android.view.ViewGroup parent, int viewType) {
            View v = android.view.LayoutInflater.from(parent.getContext()).inflate(R.layout.item_chat_bubble, parent, false);
            return new ChatViewHolder(v);
        }

        @Override
        public void onBindViewHolder(ChatViewHolder holder, int position) {
            ChatMessage m = items.get(position);
            holder.txtBubble.setText(m.text);
            holder.txtTime.setText(fmt.format(new Date(m.timestampMs)));

            // Align + background theo role
            android.widget.LinearLayout.LayoutParams lp = (android.widget.LinearLayout.LayoutParams) holder.txtBubble.getLayoutParams();
            android.widget.LinearLayout.LayoutParams lpTime = (android.widget.LinearLayout.LayoutParams) holder.txtTime.getLayoutParams();
            if (m.isUser) {
                holder.root.setGravity(android.view.Gravity.END);
                holder.txtBubble.setBackgroundResource(R.drawable.bg_bubble_user);
                holder.txtBubble.setTextColor(holder.itemView.getResources().getColor(R.color.bg_0));
                lp.gravity = android.view.Gravity.END;
                lpTime.gravity = android.view.Gravity.END;
                holder.itemView.setTranslationX(60f);
            } else {
                holder.root.setGravity(android.view.Gravity.START);
                holder.txtBubble.setBackgroundResource(R.drawable.bg_bubble_robot);
                holder.txtBubble.setTextColor(holder.itemView.getResources().getColor(R.color.text_primary));
                lp.gravity = android.view.Gravity.START;
                lpTime.gravity = android.view.Gravity.START;
                holder.itemView.setTranslationX(-60f);
            }
            holder.txtBubble.setLayoutParams(lp);
            holder.txtTime.setLayoutParams(lpTime);
            holder.itemView.setAlpha(0f);
            holder.itemView.animate().translationX(0f).alpha(1f).setDuration(240).start();
        }

        @Override
        public int getItemCount() {
            return items.size();
        }
    }

    static class ChatViewHolder extends RecyclerView.ViewHolder {
        final android.widget.LinearLayout root;
        final android.widget.TextView txtBubble;
        final android.widget.TextView txtTime;

        ChatViewHolder(View itemView) {
            super(itemView);
            root = itemView.findViewById(R.id.root);
            txtBubble = itemView.findViewById(R.id.txtBubble);
            txtTime = itemView.findViewById(R.id.txtTime);
        }
    }
}
