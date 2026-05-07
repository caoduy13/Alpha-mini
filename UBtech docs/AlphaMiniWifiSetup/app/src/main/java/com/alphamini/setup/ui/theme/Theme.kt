package com.alphamini.setup.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = BluePrimary,
    onPrimary = Color.White,
    primaryContainer = BluePrimaryLight,
    onPrimaryContainer = Color.White,
    secondary = BluePrimaryLight,
    onSecondary = Color.White,
    background = Color(0xFFF3F6FB),
    onBackground = Color(0xFF101820),
    surface = Color.White,
    onSurface = Color(0xFF101820),
    error = RedError,
    onError = Color.White
)

private val DarkColors: ColorScheme = darkColorScheme(
    primary = BluePrimaryLight,
    onPrimary = Color.Black,
    primaryContainer = BluePrimaryDark,
    onPrimaryContainer = Color.White,
    secondary = BluePrimary,
    onSecondary = Color.White,
    background = BackgroundDark,
    onBackground = Color(0xFFE3E9F5),
    surface = CardDark,
    onSurface = Color(0xFFE3E9F5),
    error = RedError,
    onError = Color.White
)

@Composable
fun AlphaMiniSetupTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colors = if (darkTheme) DarkColors else LightColors

    MaterialTheme(
        colorScheme = colors,
        typography = AppTypography,
        content = content
    )
}

