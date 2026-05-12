package com.btcpredictor.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.btcpredictor.ui.theme.AccentCyan
import com.btcpredictor.ui.theme.GaugeTrack
import com.btcpredictor.ui.theme.SignalGreen
import com.btcpredictor.ui.theme.SignalRed
import com.btcpredictor.ui.theme.TextMuted
import com.btcpredictor.ui.theme.TextSecondary

/**
 * Circular arc gauge showing conviction score (0.0 – 1.0).
 * Arc sweeps 240°: left endpoint = 0, right endpoint = 1.0.
 * Color interpolates: red (0) → cyan (0.5) → green (1.0).
 */
@Composable
fun ConvictionGauge(
    value: Float,
    modifier: Modifier = Modifier,
    size: Dp = 160.dp,
    strokeWidth: Dp = 14.dp,
    label: String = "CONVICTION",
) {
    val animatedValue by animateFloatAsState(
        targetValue = value.coerceIn(0f, 1f),
        animationSpec = tween(durationMillis = 800),
        label = "conviction",
    )

    val arcColor = convictionColor(animatedValue)

    Box(modifier = modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.size(size)) {
            val strokePx = strokeWidth.toPx()
            val padding = strokePx / 2
            val arcSize = Size(this.size.width - strokePx, this.size.height - strokePx)
            val topLeft = Offset(padding, padding)

            val sweepAngle = 240f
            val startAngle = 150f

            // Track
            drawArc(
                color = GaugeTrack,
                startAngle = startAngle,
                sweepAngle = sweepAngle,
                useCenter = false,
                topLeft = topLeft,
                size = arcSize,
                style = Stroke(width = strokePx, cap = StrokeCap.Round),
            )

            // Fill
            drawArc(
                color = arcColor,
                startAngle = startAngle,
                sweepAngle = sweepAngle * animatedValue,
                useCenter = false,
                topLeft = topLeft,
                size = arcSize,
                style = Stroke(width = strokePx, cap = StrokeCap.Round),
            )
        }

        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = "%.2f".format(animatedValue),
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
                color = arcColor,
            )
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = TextMuted,
                letterSpacing = 1.sp,
            )
        }
    }
}

private fun convictionColor(value: Float): Color = when {
    value < 0.40f -> SignalRed
    value < 0.50f -> Color(
        red = (SignalRed.red + (AccentCyan.red - SignalRed.red) * (value - 0.40f) / 0.10f),
        green = (SignalRed.green + (AccentCyan.green - SignalRed.green) * (value - 0.40f) / 0.10f),
        blue = (SignalRed.blue + (AccentCyan.blue - SignalRed.blue) * (value - 0.40f) / 0.10f),
    )
    value < 0.65f -> AccentCyan
    else -> Color(
        red = (AccentCyan.red + (SignalGreen.red - AccentCyan.red) * (value - 0.65f) / 0.35f),
        green = (AccentCyan.green + (SignalGreen.green - AccentCyan.green) * (value - 0.65f) / 0.35f),
        blue = (AccentCyan.blue + (SignalGreen.blue - AccentCyan.blue) * (value - 0.65f) / 0.35f),
    )
}
