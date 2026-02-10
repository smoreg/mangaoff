package dev.smoreg.mangaoff.ui.screens.reader

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dev.smoreg.mangaoff.data.db.ChapterDao
import dev.smoreg.mangaoff.data.repository.MangaRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

@HiltViewModel
class ReaderViewModel @Inject constructor(
    private val repository: MangaRepository,
    private val chapterDao: ChapterDao
) : ViewModel() {

    // Original pages as pairs (EN, ES) for each page number
    // Null means page doesn't exist in that language
    private val _pages = MutableStateFlow<List<Pair<File?, File?>>>(emptyList())
    val pages: StateFlow<List<Pair<File?, File?>>> = _pages.asStateFlow()

    // Page offsets removed - alignment is now done server-side
    // Pages are paired by filename (page number), so 005.jpg EN matches 005.png ES

    fun loadChapter(mangaId: String, chapterNumber: String) {
        viewModelScope.launch {
            val chapter = chapterDao.getChapter(mangaId, chapterNumber)

            if (chapter != null && chapter.isDownloaded) {
                _pages.value = repository.getChapterPages(chapter)
            }
        }
    }


    /**
     * Build bilingual page sequence.
     *
     * Pages are already aligned by page number from the server.
     * Each pair contains (EN file or null, ES file or null).
     * The reading pattern is: EN1 -> ES1 -> EN2 -> ES2 -> ...
     */
    fun getBilingualPages(
        pages: List<Pair<File?, File?>>
    ): List<BilingualPageData> {
        if (pages.isEmpty()) return emptyList()

        val result = mutableListOf<BilingualPageData>()

        for ((index, pair) in pages.withIndex()) {
            val (enFile, esFile) = pair

            // EN page (may be null if only ES exists for this page number)
            result.add(
                BilingualPageData(
                    pageNumber = index,
                    language = "en",
                    imageFile = enFile
                )
            )

            // ES page (may be null if only EN exists for this page number)
            result.add(
                BilingualPageData(
                    pageNumber = index,
                    language = "es",
                    imageFile = esFile
                )
            )
        }

        return result
    }
}
