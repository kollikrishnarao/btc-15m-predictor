package com.btcpredictor.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.btcpredictor.data.api.SessionRecord
import com.btcpredictor.ui.theme.SignalGreen
import com.btcpredictor.ui.theme.SignalGreenDim
import com.btcpredictor.ui.theme.SignalRed
import com.btcpredictor.ui.theme.SignalRedDim
import com.btcpredictor.ui.theme.SurfaceCard
import com.btcpredictor.ui.theme.SurfaceElevated
import com.btcpredictor.ui.theme.TextMuted
import com.btcpredictor.ui.theme.TextPrimary
import com.btcpredictor.ui.theme.TextSecondary

@Composable
fun SessionCard(session: SessionRecord, modifier: Modifier = Modifier) {
    val isWin = session.outcome == "WIN"
    val isGreen = session.direction == "GREEN"
    val pnlColor = if (session.totalPnl >= 0) SignalGreen else SignalRed
    val directionColor = if (isGreen) SignalGreen else SignalRed
    val outcomeColor = if (isWin) SignalGreen else SignalRed
    val outcomeBg = if (isWin) SignalGreenDim.copy(alpha = 0.15f) else SignalRedDim.copy(alpha = 0.15f)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(SurfaceCard)
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Direction dot
        Box(
            modifier = Modifier
                .size(10.dp)
                .clip(CircleShape)
                .background(directionColor)
        )

        Spacer(Modifier.width(10.dp))

        // Session info
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = session.direction,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = directionColor,
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = "conv: ${"%.2f".format(session.conviction)}",
                    style = MaterialTheme.typography.labelLarge,
                    color = TextSecondary,
                )
                if (session.flipOccurred) {
                    Spacer(Modifier.width(6.dp))
                    Text(
                        text = "FLIP",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFFBBF24),
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(Color(0xFFFBBF24).copy(alpha = 0.15f))
                            .padding(horizontal = 5.dp, vertical = 2.dp),
                    )
                }
            }
            Spacer(Modifier.height(2.dp))
            Text(
                text = formatTimestamp(session.startedAt),
                style = MaterialTheme.typography.bodyMedium,
                color = TextMuted,
            )
        }

        // Outcome + PnL
        Column(horizontalAlignment = Alignment.End) {
            Text(
                text = if (session.totalPnl >= 0) "+${"%.2f".format(session.totalPnl)}" else "${"%.2f".format(session.totalPnl)}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = pnlColor,
            )
            Spacer(Modifier.height(2.dp))
            Text(
                text = session.outcome,
                style = MaterialTheme.typography.labelLarge,
                color = outcomeColor,
                modifier = Modifier
                    .clip(RoundedCornerShape(4.dp))
                    .background(outcomeBg)
                    .padding(horizontal = 6.dp, vertical = 2.dp),
            )
        }
    }
}

private fun formatTimestamp(ts: String): String = runCatching {
    // "2026-05-12T14:30:00" → "May 12 · 14:30"
    val parts = ts.split("T")
    if (parts.size >= 2) {
        val dateParts = parts[0].split("-")
        val month = listOf("", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
            .getOrNull(dateParts.getOrNull(1)?.toIntOrNull() ?: 0) ?: ""
        val day = dateParts.getOrNull(2) ?: ""
        val time = parts[1].take(5)
        "$month $day · $time"
    } else ts
}.getOrDefault(ts)
