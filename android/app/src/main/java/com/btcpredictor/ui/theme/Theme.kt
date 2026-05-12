package com.btcpredictor.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkColorScheme = darkColorScheme(
    primary = AccentCyan,
    onPrimary = Background,
    primaryContainer = SurfaceElevated,
    onPrimaryContainer = AccentCyan,

    secondary = AccentBlue,
    onSecondary = Background,
    secondaryContainer = SurfaceCard,
    onSecondaryContainer = TextPrimary,

    tertiary = SignalGreen,
    onTertiary = Background,

    background = Background,
    onBackground = TextPrimary,

    surface = SurfaceCard,
    onSurface = TextPrimary,
    surfaceVariant = SurfaceElevated,
    onSurfaceVariant = TextSecondary,

    outline = Border,
    outlineVariant = TextMuted,

    error = SignalRed,
    onError = Color.White,

    inverseSurface = TextPrimary,
    inverseOnSurface = Background,
    inversePrimary = AccentCyanDim,
)

@Composable
fun BtcPredictorTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = Typography,
        content = content,
    )
}
