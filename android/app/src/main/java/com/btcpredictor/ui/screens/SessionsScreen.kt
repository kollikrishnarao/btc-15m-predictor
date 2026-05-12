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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.btcpredictor.ui.components.SessionCard
import com.btcpredictor.ui.theme.AccentCyan
import com.btcpredictor.ui.theme.Background
import com.btcpredictor.ui.theme.SignalGreen
import com.btcpredictor.ui.theme.SignalRed
import com.btcpredictor.ui.theme.TextMuted
import com.btcpredictor.ui.theme.TextSecondary
import com.btcpredictor.ui.viewmodel.SessionsState
import com.btcpredictor.ui.viewmodel.SessionsViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionsScreen(viewModel: SessionsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        when (val s = state) {
            is SessionsState.Loading -> {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center),
                    color = AccentCyan,
                )
            }

            is SessionsState.Error -> {
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

            is SessionsState.Success -> {
                val sessions = s.sessions
                val wins = sessions.count { it.outcome == "WIN" }
                val losses = sessions.count { it.outcome == "LOSS" }

                PullToRefreshBox(
                    isRefreshing = false,
                    onRefresh = viewModel::load,
                ) {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        item {
                            Spacer(Modifier.height(12.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column {
                                    Text("Sessions", style = MaterialTheme.typography.headlineMedium)
                                    Text(
                                        text = "${sessions.size} total · $wins W · $losses L",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = TextMuted,
                                    )
                                }
                                Row {
                                    Text("$wins", style = MaterialTheme.typography.titleMedium, color = SignalGreen)
                                    Text(" / ", style = MaterialTheme.typography.titleMedium, color = TextMuted)
                                    Text("$losses", style = MaterialTheme.typography.titleMedium, color = SignalRed)
                                    IconButton(onClick = viewModel::load) {
                                        Icon(Icons.Default.Refresh, contentDescription = null, tint = TextSecondary)
                                    }
                                }
                            }
                            Spacer(Modifier.height(8.dp))
                        }

                        if (sessions.isEmpty()) {
                            item {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(top = 80.dp),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    Text("No sessions yet", style = MaterialTheme.typography.bodyLarge, color = TextMuted)
                                }
                            }
                        } else {
                            items(sessions, key = { it.sessionId }) { session ->
                                SessionCard(session = session)
                            }
                        }

                        item { Spacer(Modifier.height(80.dp)) }
                    }
                }
            }
        }
    }
}
