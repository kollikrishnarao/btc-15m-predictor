package com.btcpredictor.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import com.btcpredictor.data.api.SignalsPayload
import com.btcpredictor.ui.components.ConvictionGauge
import com.btcpredictor.ui.components.DimensionData
import com.btcpredictor.ui.components.SignalDimensionsCard
import com.btcpredictor.ui.components.StatChip
import com.btcpredictor.ui.theme.AccentCyan
import com.btcpredictor.ui.theme.AlertCritical
import com.btcpredictor.ui.theme.AlertWarning
import com.btcpredictor.ui.theme.Background
import com.btcpredictor.ui.theme.Border
import com.btcpredictor.ui.theme.SignalGreen
import com.btcpredictor.ui.theme.SignalRed
import com.btcpredictor.ui.theme.SurfaceCard
import com.btcpredictor.ui.theme.SurfaceElevated
import com.btcpredictor.ui.theme.TextMuted
import com.btcpredictor.ui.theme.TextPrimary
import com.btcpredictor.ui.theme.TextSecondary
import com.btcpredictor.ui.viewmodel.DashboardState
import com.btcpredictor.ui.viewmodel.DashboardViewModel

@Composable
fun DashboardScreen(viewModel: DashboardViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        when (val s = state) {
            is DashboardState.Loading -> {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center),
                    color = AccentCyan,
                )
            }

            is DashboardState.Error -> {
                ErrorState(
                    message = s.message,
                    onRetry = viewModel::refresh,
                    modifier = Modifier.align(Alignment.Center),
                )
            }

            is DashboardState.Success -> {
                DashboardContent(
                    payload = s.payload,
                    onRefresh = viewModel::refresh,
                )
            }
        }
    }
}

@Composable
private fun DashboardContent(
    payload: SignalsPayload,
    onRefresh: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // ── Header ────────────────────────────────────────────────────────────
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("BTC 15m Predictor", style = MaterialTheme.typography.headlineMedium)
                Text(
                    text = cyclePhaseLabel(payload.system.cyclePhase),
                    style = MaterialTheme.typography.bodyMedium,
                    color = cyclePhaseColor(payload.system.cyclePhase),
                )
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                // Live indicator dot
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(if (payload.system.isRunning) SignalGreen else TextMuted)
                )
                IconButton(onClick = onRefresh) {
                    Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = TextSecondary)
                }
            }
        }

        // ── BTC Price row ─────────────────────────────────────────────────────
        BtcPriceCard(payload)

        // ── Circuit breaker warning ───────────────────────────────────────────
        if (payload.system.circuitBreaker == "TRIPPED") {
            CircuitBreakerBanner()
        }

        // ── Conviction gauge + call ───────────────────────────────────────────
        ConvictionSection(payload)

        // ── Active session ────────────────────────────────────────────────────
        if (payload.activeSession != null) {
            ActiveSessionCard(payload)
        }

        // ── Signal dimensions ─────────────────────────────────────────────────
        val dims = buildDimensions(payload)
        SignalDimensionsCard(dimensions = dims)

        // ── Orderflow metrics ─────────────────────────────────────────────────
        OrderflowCard(payload)

        // ── Market metrics ────────────────────────────────────────────────────
        MarketMetricsRow(payload)

        Spacer(Modifier.height(80.dp)) // bottom nav clearance
    }
}

@Composable
private fun BtcPriceCard(payload: SignalsPayload) {
    val change = payload.market.priceChangePct24h
    val changeColor = if (change >= 0) SignalGreen else SignalRed
    val changeSign = if (change >= 0) "+" else ""

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceCard)
            .padding(16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column {
            Text("BTC / USDT", style = MaterialTheme.typography.labelLarge, color = TextMuted)
            Text(
                text = "$${"%,.0f".format(payload.market.btcPrice)}",
                fontSize = 30.sp,
                fontWeight = FontWeight.Bold,
                color = TextPrimary,
            )
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                text = "${changeSign}${"%.2f".format(change)}%",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = changeColor,
            )
            Text(
                text = "24h change",
                style = MaterialTheme.typography.labelSmall,
                color = TextMuted,
            )
        }
    }
}

@Composable
private fun ConvictionSection(payload: SignalsPayload) {
    val conviction = payload.conviction.weightedTotal.toFloat()
    val lastDir = payload.lastDirection
    val directionColor = when (lastDir) {
        "GREEN" -> SignalGreen
        "RED" -> SignalRed
        else -> TextMuted
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceCard)
            .padding(16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        ConvictionGauge(
            value = conviction,
            size = 150.dp,
        )
        Column(
            horizontalAlignment = Alignment.End,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Column(horizontalAlignment = Alignment.End) {
                Text("LAST CALL", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                Text(
                    text = lastDir,
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Bold,
                    color = directionColor,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("ADVISOR", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                Text(
                    text = "${payload.advisorCall} @ ${"%.0f".format(payload.advisorConfidence * 100)}%",
                    style = MaterialTheme.typography.bodyMedium,
                    color = when (payload.advisorCall) {
                        "GREEN" -> SignalGreen
                        "RED" -> SignalRed
                        else -> TextSecondary
                    },
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("VPIN", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                val vpinColor = when {
                    payload.orderflow.vpin > 0.70 -> AlertCritical
                    payload.orderflow.vpin > 0.50 -> AlertWarning
                    else -> AccentCyan
                }
                Text(
                    text = "%.3f".format(payload.orderflow.vpin),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = vpinColor,
                )
            }
        }
    }
}

@Composable
private fun ActiveSessionCard(payload: SignalsPayload) {
    val session = payload.activeSession ?: return
    val dirColor = if (session.direction == "GREEN") SignalGreen else SignalRed

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(dirColor.copy(alpha = 0.10f))
            .padding(16.dp),
    ) {
        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "● ACTIVE SESSION",
                style = MaterialTheme.typography.labelLarge,
                color = dirColor,
            )
            Text(
                text = "Bet ${session.betNumber} of 3",
                style = MaterialTheme.typography.labelLarge,
                color = TextSecondary,
            )
        }
        Spacer(Modifier.height(10.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            StatChip("DIRECTION", session.direction, dirColor)
            StatChip("BET SIZE", "\$${session.currentBetSize.toInt()}", TextPrimary)
            StatChip("AT RISK", "\$${session.totalAtRisk.toInt()}", AlertWarning)
            StatChip("TARGET", session.candleTarget, AccentCyan)
        }
    }
}

@Composable
private fun OrderflowCard(payload: SignalsPayload) {
    val of = payload.orderflow
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceCard)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            "ORDERFLOW METRICS",
            style = MaterialTheme.typography.labelLarge,
            color = TextSecondary,
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            StatChip("VPIN", "%.3f".format(of.vpin), vpinColor(of.vpin))
            StatChip("TCR", "${if (of.tcr >= 0) "+" else ""}${"%.3f".format(of.tcr)}", AccentCyan)
            StatChip("OBI", "${if (of.obi >= 0) "+" else ""}${"%.3f".format(of.obi)}", AccentCyan)
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            StatChip("CVD", "${if (of.cvd >= 0) "+" else ""}${"%.0f".format(of.cvd)}", AccentCyan)
            StatChip("OFI", "${if (of.ofi >= 0) "+" else ""}${"%.3f".format(of.ofi)}", AccentCyan)
            StatChip(
                "CVD DIV",
                if (of.cvdDivergence) "YES" else "NO",
                if (of.cvdDivergence) AlertWarning else TextMuted,
            )
        }
    }
}

@Composable
private fun MarketMetricsRow(payload: SignalsPayload) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        StatChip(
            label = "FEAR/GREED",
            value = payload.market.fearGreedIndex.toString(),
            valueColor = fearGreedColor(payload.market.fearGreedIndex),
            modifier = Modifier.weight(1f),
        )
        StatChip(
            label = "ADX",
            value = "%.1f".format(payload.market.adx),
            valueColor = if (payload.market.adx >= 25) SignalGreen else TextMuted,
            modifier = Modifier.weight(1f),
        )
        StatChip(
            label = "RVOL",
            value = "%.2f".format(payload.market.rvol),
            valueColor = if (payload.market.rvol >= 1.5) SignalGreen else TextPrimary,
            modifier = Modifier.weight(1f),
        )
        StatChip(
            label = "FUNDING",
            value = "${"%.4f".format(payload.market.fundingRate)}%",
            valueColor = if (Math.abs(payload.market.fundingRate) > 0.10) AlertWarning else TextPrimary,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun CircuitBreakerBanner() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(AlertCritical.copy(alpha = 0.15f))
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(Icons.Default.Warning, contentDescription = null, tint = AlertCritical, modifier = Modifier.size(20.dp))
        Text(
            "CIRCUIT BREAKER ACTIVE — Trading paused",
            style = MaterialTheme.typography.bodyMedium,
            color = AlertCritical,
        )
    }
}

@Composable
private fun ErrorState(message: String, onRetry: () -> Unit, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(Icons.Default.Warning, contentDescription = null, tint = AlertWarning, modifier = Modifier.size(48.dp))
        Text("Connection Error", style = MaterialTheme.typography.titleLarge, color = TextPrimary)
        Text(message, style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
        androidx.compose.material3.Button(onClick = onRetry) {
            Text("Retry")
        }
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

private fun buildDimensions(payload: SignalsPayload): List<DimensionData> {
    val c = payload.conviction
    return listOf(
        DimensionData("momentum", "Momentum", c.momentum.toFloat(), 0.25f),
        DimensionData("trend", "Trend", c.trend.toFloat(), 0.20f),
        DimensionData("orderflow", "Orderflow", c.orderflow.toFloat(), 0.20f),
        DimensionData("smart_money", "Smart Money", c.smartMoney.toFloat(), 0.15f),
        DimensionData("sentiment", "Sentiment", c.sentiment.toFloat(), 0.10f),
        DimensionData("macro", "Macro", c.macro.toFloat(), 0.10f),
    )
}

private fun vpinColor(vpin: Double): Color = when {
    vpin > 0.70 -> AlertCritical
    vpin > 0.50 -> AlertWarning
    else -> AccentCyan
}

private fun fearGreedColor(index: Int): Color = when {
    index < 25 -> SignalGreen  // extreme fear = contrarian bullish
    index < 45 -> Color(0xFF00C853)
    index < 55 -> AccentCyan
    index < 75 -> AlertWarning
    else -> SignalRed
}

private fun cyclePhaseLabel(phase: String): String = when (phase) {
    "ANALYZING" -> "⟳ Analyzing signals..."
    "WAITING" -> "⏳ Waiting for C2 close"
    "RESOLVING" -> "⚡ Resolving bet"
    "IDLE" -> "Ready — next cycle in..."
    "STOPPED" -> "System stopped"
    else -> phase
}

private fun cyclePhaseColor(phase: String): Color = when (phase) {
    "ANALYZING" -> AccentCyan
    "WAITING" -> AlertWarning
    "RESOLVING" -> SignalGreen
    "STOPPED" -> SignalRed
    else -> TextSecondary
}
