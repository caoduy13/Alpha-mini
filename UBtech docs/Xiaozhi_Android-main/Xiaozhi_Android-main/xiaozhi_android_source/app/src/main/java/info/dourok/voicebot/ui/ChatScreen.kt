package info.dourok.voicebot.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.sp

@Composable
fun ChatScreen(
    viewModel: ChatViewMode = hiltViewModel()
) {
    val messages by viewModel.display.chatFlow.collectAsState()
    val emotion by viewModel.display.emotionFlow.collectAsState()
    val deviceState by viewModel.deviceStateFlow.collectAsState() // Added device state
    // Emotion to emoji mapping
    val emotionEmojiMap = mapOf(
        "neutral" to "😐",
        "happy" to "😊",
        "laughing" to "😂",
        "funny" to "🤡",
        "sad" to "😢",
        "angry" to "😠",
        "crying" to "😭",
        "loving" to "🥰",
        "embarrassed" to "😳",
        "surprised" to "😮",
        "shocked" to "😱",
        "thinking" to "🤔",
        "winking" to "😉",
        "cool" to "😎",
        "relaxed" to "😌",
        "delicious" to "😋",
        "kissy" to "😘",
        "confident" to "😏",
        "sleepy" to "😴",
        "silly" to "🤪",
        "confused" to "😕"
    )
    Column(
        modifier = Modifier
            .fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Emotion display at top center with bigger emoji
        Box(
            modifier = Modifier
                .padding(vertical = 16.dp),
            contentAlignment = Alignment.Center
        ) {
            when (deviceState) {
                DeviceState.CONNECTING, DeviceState.STARTING -> {
                    CircularProgressIndicator(
                        modifier = Modifier.size(64.dp), // 与emoji大小匹配
                        strokeWidth = 4.dp,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                else -> {
                    Text(
                        text = emotionEmojiMap[emotion.lowercase()] ?: "😐",
                        style = TextStyle(
                            fontSize = 64.sp,
                            lineHeight = 64.sp
                        )
                    )
                }
            }
        }

        // Device State Text
        Text(
            text = deviceState.name.lowercase()
                .replaceFirstChar { it.uppercase() },
            style = MaterialTheme.typography.bodySmall,
            color = when (deviceState) {
                DeviceState.FATAL_ERROR -> MaterialTheme.colorScheme.error
                else -> MaterialTheme.colorScheme.onSurface
            },
            modifier = Modifier.padding(bottom = 8.dp)
        )

        LazyColumn(
            modifier = Modifier
                .weight(1f),
            reverseLayout = true,
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(messages.reversed()) { message ->
                ChatMessageItem(message)
            }
        }
    }
}


@Composable
fun ChatMessageItem(message: Message) {
    val isCurrentUser = message.sender == "user"

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp),
        horizontalArrangement = if (isCurrentUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (isCurrentUser)
                    MaterialTheme.colorScheme.primary
                else
                    MaterialTheme.colorScheme.surfaceVariant
            ),
            modifier = Modifier.widthIn(max = 300.dp)
        ) {
            Column(
                modifier = Modifier.padding(12.dp)
            ) {
                Text(
                    text = message.sender,
                    style = MaterialTheme.typography.labelLarge,
                    color = if (isCurrentUser)
                        MaterialTheme.colorScheme.onPrimary
                    else
                        MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = message.message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (isCurrentUser)
                        MaterialTheme.colorScheme.onPrimary
                    else
                        MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp)
                )
                Text(
                    text = message.nowInString,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (isCurrentUser)
                        MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.7f)
                    else
                        MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                    modifier = Modifier
                        .padding(top = 4.dp)
                        .align(Alignment.End)
                )
            }
        }
    }
}
