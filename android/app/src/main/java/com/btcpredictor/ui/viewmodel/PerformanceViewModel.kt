package com.btcpredictor.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.btcpredictor.data.api.PerformanceStats
import com.btcpredictor.data.repository.PredictorRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed class PerformanceState {
    data object Loading : PerformanceState()
    data class Success(val stats: PerformanceStats) : PerformanceState()
    data class Error(val message: String) : PerformanceState()
}

@HiltViewModel
class PerformanceViewModel @Inject constructor(
    private val repository: PredictorRepository,
) : ViewModel() {

    private val _state = MutableStateFlow<PerformanceState>(PerformanceState.Loading)
    val state: StateFlow<PerformanceState> = _state.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = PerformanceState.Loading
            repository.getPerformance()
                .onSuccess { _state.value = PerformanceState.Success(it) }
                .onFailure { _state.value = PerformanceState.Error(it.message ?: "Error") }
        }
    }
}
