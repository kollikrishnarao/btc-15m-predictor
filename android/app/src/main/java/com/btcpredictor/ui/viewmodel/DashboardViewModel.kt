package com.btcpredictor.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.btcpredictor.data.api.SignalsPayload
import com.btcpredictor.data.repository.PredictorRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed class DashboardState {
    data object Loading : DashboardState()
    data class Success(val payload: SignalsPayload) : DashboardState()
    data class Error(val message: String) : DashboardState()
}

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val repository: PredictorRepository,
) : ViewModel() {

    private val _state = MutableStateFlow<DashboardState>(DashboardState.Loading)
    val state: StateFlow<DashboardState> = _state.asStateFlow()

    init {
        loadSignals()
        startWebSocket()
    }

    fun loadSignals() {
        viewModelScope.launch {
            _state.value = DashboardState.Loading
            repository.getSignals()
                .onSuccess { _state.value = DashboardState.Success(it) }
                .onFailure { _state.value = DashboardState.Error(it.message ?: "Unknown error") }
        }
    }

    fun refresh() = loadSignals()

    private fun startWebSocket() {
        repository.liveUpdates()
            .onEach { msg ->
                if (msg.type == "SIGNALS_UPDATE") {
                    repository.getSignals()
                        .onSuccess { _state.value = DashboardState.Success(it) }
                }
            }
            .catch { /* reconnect handled by WsClient */ }
            .launchIn(viewModelScope)
    }
}
