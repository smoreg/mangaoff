package dev.smoreg.mangaoff.ui.screens.chapters

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dev.smoreg.mangaoff.data.db.ChapterEntity
import dev.smoreg.mangaoff.data.repository.MangaRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ChapterListViewModel @Inject constructor(
    private val repository: MangaRepository
) : ViewModel() {

    private var currentMangaId: String = ""

    private val _chapters = MutableStateFlow<List<ChapterEntity>>(emptyList())
    val chapters: StateFlow<List<ChapterEntity>> = _chapters.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _downloadProgress = MutableStateFlow(0f)
    val downloadProgress: StateFlow<Float> = _downloadProgress.asStateFlow()

    private val _downloadingChapter = MutableStateFlow<String?>(null)
    val downloadingChapter: StateFlow<String?> = _downloadingChapter.asStateFlow()

    private val _isDownloadingAll = MutableStateFlow(false)
    val isDownloadingAll: StateFlow<Boolean> = _isDownloadingAll.asStateFlow()

    private val _downloadAllProgress = MutableStateFlow(0f)
    val downloadAllProgress: StateFlow<Float> = _downloadAllProgress.asStateFlow()

    fun loadChapters(mangaId: String) {
        if (currentMangaId == mangaId) return
        currentMangaId = mangaId

        viewModelScope.launch {
            repository.getChaptersForManga(mangaId).collect { chapters ->
                _chapters.value = chapters
            }
        }

        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _isLoading.value = true
            repository.refreshChapters(currentMangaId)
            _isLoading.value = false
        }
    }

    fun downloadChapter(chapter: ChapterEntity) {
        if (_downloadingChapter.value != null || _isDownloadingAll.value) return

        viewModelScope.launch {
            _downloadingChapter.value = chapter.number
            _downloadProgress.value = 0f

            repository.downloadChapter(chapter) { progress ->
                _downloadProgress.value = progress
            }

            _downloadingChapter.value = null
            _downloadProgress.value = 0f
        }
    }

    fun downloadAllChapters() {
        if (_isDownloadingAll.value || _downloadingChapter.value != null) return

        viewModelScope.launch {
            _isDownloadingAll.value = true
            _downloadAllProgress.value = 0f

            val notDownloaded = _chapters.value.filter { !it.isDownloaded }
            val total = notDownloaded.size

            notDownloaded.forEachIndexed { index, chapter ->
                _downloadingChapter.value = chapter.number
                _downloadProgress.value = 0f

                repository.downloadChapter(chapter) { progress ->
                    _downloadProgress.value = progress
                    _downloadAllProgress.value = (index + progress) / total
                }

                _downloadingChapter.value = null
            }

            _isDownloadingAll.value = false
            _downloadAllProgress.value = 0f
        }
    }

    fun deleteChapter(chapter: ChapterEntity) {
        viewModelScope.launch {
            repository.deleteChapter(chapter)
        }
    }

    fun cancelDownloadAll() {
        _isDownloadingAll.value = false
    }
}
