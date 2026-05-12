package com.btcpredictor.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.btcpredictor.data.api.PerformanceStats
import com.btcpredictor.ui.components.StatChip
import com.btcpredictor.ui.theme.AccentCyan
import com.btcpredictor.ui.theme.Background
import com.btcpredictor.ui.theme.GaugeTrack
import com.btcpredictor.ui.theme.SignalGreen
import com.btcpredictor.ui.theme.SignalRed
import com.btcpredictor.ui.theme.SurfaceCard
import com.btcpredictor.ui.theme.SurfaceElevated
import com.btcpredictor.ui.theme.TextMuted
import com.btcpredictor.ui.theme.TextPrimary
import com.btcpredictor.ui.theme.TextSecondary
import com.btcpredictor.ui.viewmodel.PerformanceState
import com.btcpredictor.ui.viewmodel.PerformanceViewModel

@Composable
fun PerformanceScreen(viewModel: PerformanceViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        when (val s = state) {
            is PerformanceState.Loading -> {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center),
                    color = AccentCyan,
                )
            }

            is PerformanceState.Error -> {
                Column(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(s.message, color = TextSecondary)
                    Spacer(Modifier.height(12.dp))
                    androidx.compose.material3.Button(onClick = viewModel::load) { Text("Retry") }
                }
            }

            is PerformanceState.Success -> {
                PerformanceContent(stats = s.stats, onRefresh = viewModel::load)
            }
        }
    }
}

@Composable
private fun PerformanceContent(stats: PerformanceStats, onRefresh: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Performance", style = MaterialTheme.typography.headlineMedium)
            IconButton(onClick = onRefresh) {
                Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = TextSecondary)
            }
        }

        // Bankroll hero card
        BankrollCard(stats)

        // Win rate section
        WinRateCard(stats)

        // P&L breakdown
        PnlCard(stats)

        // Dimension accuracy
        DimensionAccuracyCard(stats)

        Spacer(Modifier.height(80.dp))
    }
}

@Composable
private fun BankrollCard(stats: PerformanceStats) {
    val pnlColor = if (stats.totalPnl >= 0) SignalGreen else SignalRed

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceCard)
            .padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text("BANKROLL", style = MaterialTheme.typography.labelLarge, color = TextMuted)
        Text(
            text = "\$${"%.2f".format(stats.bankroll)}",
            fontSize = 40.sp,
            fontWeight = FontWeight.Bold,
            color = TextPrimary,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Total P&L:", style = MaterialTheme.typography.bodyMedium, color = TextMuted)
            Text(
                text = "${if (stats.totalPnl >= 0) "+" else ""}\$${"%.2f".format(stats.totalPnl)}",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = pnlColor,
            )
        }
        Spacer(Modifier.height(8.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            StatChip("SESSIONS", stats.totalSessions.toString(), AccentCyan)
            StatChip(
                "WIN STREAK",
                stats.consecutiveWins.toString(),
                if (stats.consecutiveWins > 0) SignalGreen else TextMuted,
            )
            StatChip(
                "LOSS STREAK",
                stats.consecutiveLosses.toString(),
                if (stats.consecutiveLosses > 0) SignalRed else TextMuted,
            )
        }
    }
}

@Composable
private fun WinRateCard(stats: PerformanceStats) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceCard)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("WIN RATE", style = MaterialTheme.typography.labelLarge, color = TextSecondary)

        WinRateBar(
            label = "Rolling 20",
            rate = stats.winRate20.toFloat(),
            target = 0.50f,
        )
        WinRateBar(
            label = "All Time",
            rate = stats.winRateAll.toFloat(),
            target = 0.50f,
        )

        Spacer(Modifier.height(4.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column {
                Text("Avg conv on WINS", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                Text(
                    "%.3f".format(stats.avgConvictionOnWins),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = SignalGreen,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("Avg conv on LOSSES", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                Text(
                    "%.3f".format(stats.avgConvictionOnLosses),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = SignalRed,
                )
            }
        }
    }
}

@Composable
private fun WinRateBar(label: String, rate: Float, target: Float) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(label, style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
            Text(
                "${"%.1f".format(rate * 100)}%",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = if (rate >= target) SignalGreen else SignalRed,
            )
        }
        LinearProgressIndicator(
            progress = { rate.coerceIn(0f, 1f) },
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(3.dp)),
            color = if (rate >= target) SignalGreen else SignalRed,
            trackColor = GaugeTrack,
        )
    }
}

@Composable
private fun PnlCard(stats: PerformanceStats) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceCard)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("P&L BREAKDOWN", style = MaterialTheme.typography.labelLarge, color = TextSecondary)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            StatChip(
                "TODAY",
                "${if (stats.dailyPnl >= 0) "+" else ""}\$${"%.2f".format(stats.dailyPnl)}",
                if (stats.dailyPnl >= 0) SignalGreen else SignalRed,
            )
            StatChip(
                "7 DAYS",
                "${if (stats.weeklyPnl >= 0) "+" else ""}\$${"%.2f".format(stats.weeklyPnl)}",
                if (stats.weeklyPnl >= 0) SignalGreen else SignalRed,
            )
            StatChip(
                "ALL TIME",
                "${if (stats.totalPnl >= 0) "+" else ""}\$${"%.2f".format(stats.totalPnl)}",
                if (stats.totalPnl >= 0) SignalGreen else SignalRed,
            )
        }
    }
}

@Composable
private fun DimensionAccuracyCard(stats: PerformanceStats) {
    if (stats.dimensionAccuracy.isEmpty()) return

    val dimLabels = mapOf(
        "momentum" to "Momentum",
        "trend" to "Trend",
        "orderflow" to "Orderflow",
        "smart_money" to "Smart Money",
        "sentiment" to "Sentiment",
        "macro" to "Macro",
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceCard)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text("DIMENSION ACCURACY", style = MaterialTheme.typography.labelLarge, color = TextSecondary)
            Column(horizontalAlignment = Alignment.End) {
                Text("best: ${dimLabels[stats.bestDimension] ?: stats.bestDimension}", style = MaterialTheme.typography.labelSmall, color = SignalGreen)
                Text("worst: ${dimLabels[stats.worstDimension] ?: stats.worstDimension}", style = MaterialTheme.typography.labelSmall, color = SignalRed)
            }
        }

        stats.dimensionAccuracy.entries
            .sortedByDescending { it.value }
            .forEach { (dim, acc) ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        text = dimLabels[dim] ?: dim,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.width(100.dp),
                        color = TextPrimary,
                    )
                    LinearProgressIndicator(
                        progress = { acc.toFloat().coerceIn(0f, 1f) },
                        modifier = Modifier
                            .weight(1f)
                            .height(5.dp)
                            .clip(RoundedCornerShape(3.dp)),
                        color = if (acc >= 0.55) SignalGreen else if (acc >= 0.45) AccentCyan else SignalRed,
                        trackColor = GaugeTrack,
                    )
                    Text(
                        text = "${"%.0f".format(acc * 100)}%",
                        style = MaterialTheme.typography.labelLarge,
                        color = if (acc >= 0.55) SignalGreen else if (acc >= 0.45) AccentCyan else SignalRed,
                        modifier = Modifier.width(36.dp),
                    )
                }
            }
    }
}
