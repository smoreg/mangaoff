package dev.smoreg.mangaoff.ui.screens.mangalist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dev.smoreg.mangaoff.data.db.MangaEntity
import dev.smoreg.mangaoff.data.repository.MangaRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MangaListViewModel @Inject constructor(
    private val repository: MangaRepository
) : ViewModel() {

    private val _mangaList = MutableStateFlow<List<MangaEntity>>(emptyList())
    val mangaList: StateFlow<List<MangaEntity>> = _mangaList.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    init {
        viewModelScope.launch {
            repository.getAllManga().collect { manga ->
                _mangaList.value = manga
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _isLoading.value = true
            _error.value = null

            repository.refreshMangaList()
                .onFailure { e ->
                    _error.value = e.message ?: "Failed to load manga"
                }

            _isLoading.value = false
        }
    }
}
