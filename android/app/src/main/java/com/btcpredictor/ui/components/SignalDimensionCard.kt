package com.btcpredictor.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.btcpredictor.ui.theme.AccentCyan
import com.btcpredictor.ui.theme.Border
import com.btcpredictor.ui.theme.GaugeTrack
import com.btcpredictor.ui.theme.SignalGreen
import com.btcpredictor.ui.theme.SignalRed
import com.btcpredictor.ui.theme.SurfaceCard
import com.btcpredictor.ui.theme.TextMuted
import com.btcpredictor.ui.theme.TextPrimary
import com.btcpredictor.ui.theme.TextSecondary

data class DimensionData(
    val name: String,
    val label: String,
    val score: Float,
    val weight: Float,
)

@Composable
fun SignalDimensionRow(dimension: DimensionData, modifier: Modifier = Modifier) {
    val animatedScore by animateFloatAsState(
        targetValue = dimension.score.coerceIn(0f, 1f),
        animationSpec = tween(600),
        label = "score_${dimension.name}",
    )

    val barColor = dimensionBarColor(dimension.score)
    val signalText = dimensionSignalText(dimension.score)

    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(
                    text = dimension.label,
                    style = MaterialTheme.typography.titleMedium,
                    color = TextPrimary,
                )
                Text(
                    text = "weight ${(dimension.weight * 100).toInt()}%",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextMuted,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = "%.2f".format(animatedScore),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = barColor,
                )
                Text(
                    text = signalText,
                    style = MaterialTheme.typography.labelSmall,
                    color = barColor,
                )
            }
        }

        Spacer(Modifier.height(6.dp))

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(3.dp))
                .background(GaugeTrack)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(animatedScore)
                    .height(6.dp)
                    .clip(RoundedCornerShape(3.dp))
                    .background(barColor)
            )
        }
    }
}

@Composable
fun SignalDimensionsCard(
    dimensions: List<DimensionData>,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceCard)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text(
            text = "SIGNAL DIMENSIONS",
            style = MaterialTheme.typography.labelLarge,
            color = TextSecondary,
            letterSpacing = androidx.compose.ui.unit.TextUnit(1.2f, androidx.compose.ui.unit.TextUnitType.Sp),
        )
        dimensions.forEach { dim ->
            SignalDimensionRow(dimension = dim)
        }
    }
}

private fun dimensionBarColor(score: Float): Color = when {
    score < 0.35f -> SignalRed
    score < 0.50f -> Color(0xFFFF8C00)
    score < 0.65f -> AccentCyan
    else -> SignalGreen
}

private fun dimensionSignalText(score: Float): String = when {
    score < 0.25f -> "STRONG BEAR"
    score < 0.35f -> "BEAR"
    score < 0.45f -> "SLIGHT BEAR"
    score < 0.55f -> "NEUTRAL"
    score < 0.65f -> "SLIGHT BULL"
    score < 0.75f -> "BULL"
    else -> "STRONG BULL"
}
