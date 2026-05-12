package com.btcpredictor.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.btcpredictor.data.api.SessionRecord
import com.btcpredictor.data.repository.PredictorRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed class SessionsState {
    data object Loading : SessionsState()
    data class Success(val sessions: List<SessionRecord>) : SessionsState()
    data class Error(val message: String) : SessionsState()
}

@HiltViewModel
class SessionsViewModel @Inject constructor(
    private val repository: PredictorRepository,
) : ViewModel() {

    private val _state = MutableStateFlow<SessionsState>(SessionsState.Loading)
    val state: StateFlow<SessionsState> = _state.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = SessionsState.Loading
            repository.getSessions(limit = 100)
                .onSuccess { _state.value = SessionsState.Success(it) }
                .onFailure { _state.value = SessionsState.Error(it.message ?: "Error") }
        }
    }
}
