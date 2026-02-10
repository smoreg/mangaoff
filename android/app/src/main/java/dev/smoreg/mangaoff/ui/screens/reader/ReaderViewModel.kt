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
    private val _pages = MutableStateFlow<List<Pair<File, File>>>(emptyList())
    val pages: StateFlow<List<Pair<File, File>>> = _pages.asStateFlow()

    // Page offsets for handling translation discrepancies
    // Positive offset = skip pages at start, negative = add blanks
    private val _enOffset = MutableStateFlow(0)
    val enOffset: StateFlow<Int> = _enOffset.asStateFlow()

    private val _esOffset = MutableStateFlow(0)
    val esOffset: StateFlow<Int> = _esOffset.asStateFlow()

    fun loadChapter(mangaId: String, chapterNumber: String) {
        viewModelScope.launch {
            val chapter = chapterDao.getChapter(mangaId, chapterNumber)

            if (chapter != null && chapter.isDownloaded) {
                _pages.value = repository.getChapterPages(chapter)
            }
        }
    }

    fun setEnOffset(offset: Int) {
        _enOffset.value = offset.coerceIn(-10, 10)
    }

    fun setEsOffset(offset: Int) {
        _esOffset.value = offset.coerceIn(-10, 10)
    }

    /**
     * Build bilingual page sequence with offsets applied.
     *
     * The reading pattern is: EN1 -> ES1 -> EN2 -> ES2 -> ...
     * Offsets allow adjusting which actual file is shown for each logical page.
     *
     * Example with enOffset=1:
     * - Logical page 0 EN -> shows EN file at index 1
     * - Logical page 0 ES -> shows ES file at index 0
     *
     * This handles cases where one translation has an extra cover page.
     */
    fun getBilingualPages(
        pages: List<Pair<File, File>>,
        enOffset: Int,
        esOffset: Int
    ): List<BilingualPageData> {
        if (pages.isEmpty()) return emptyList()

        val result = mutableListOf<BilingualPageData>()

        // Find the maximum logical page count considering offsets
        val enFiles = pages.map { it.first }
        val esFiles = pages.map { it.second }

        // Calculate effective range
        val enEffectiveStart = maxOf(0, enOffset)
        val esEffectiveStart = maxOf(0, esOffset)
        val enEffectiveEnd = enFiles.size
        val esEffectiveEnd = esFiles.size

        // Determine how many logical pages we have
        val enLogicalCount = enEffectiveEnd - enEffectiveStart
        val esLogicalCount = esEffectiveEnd - esEffectiveStart
        val logicalPageCount = maxOf(enLogicalCount, esLogicalCount)

        for (logicalPage in 0 until logicalPageCount) {
            // Calculate actual file indices
            val enFileIndex = logicalPage + enOffset
            val esFileIndex = logicalPage + esOffset

            // EN page
            result.add(
                BilingualPageData(
                    pageNumber = logicalPage,
                    language = "en",
                    imageFile = enFiles.getOrNull(enFileIndex)
                )
            )

            // ES page
            result.add(
                BilingualPageData(
                    pageNumber = logicalPage,
                    language = "es",
                    imageFile = esFiles.getOrNull(esFileIndex)
                )
            )
        }

        return result
    }
}
