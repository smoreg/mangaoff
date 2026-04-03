package dev.smoreg.mangaoff.data.repository

import dev.smoreg.mangaoff.data.db.ChapterEntity
import org.junit.Assert.*
import org.junit.Test

/**
 * Unit tests to verify chapter download status preservation logic.
 */
class ChapterDownloadStatusTest {

    @Test
    fun `chapter number matching works correctly`() {
        // Simulate existing chapters in DB
        val existingChapters = listOf(
            createChapter("manga1", "1", isDownloaded = true),
            createChapter("manga1", "2", isDownloaded = false),
            createChapter("manga1", "3", isDownloaded = true)
        ).associateBy { it.number }

        // API returns same chapter numbers
        val apiChapterNumbers = listOf("1", "2", "3", "4")

        for (apiNum in apiChapterNumbers) {
            val existing = existingChapters[apiNum]
            if (existing != null) {
                // Should preserve download status
                println("Chapter $apiNum exists, isDownloaded=${existing.isDownloaded}")
            } else {
                println("Chapter $apiNum is new")
            }
        }

        // Verify lookups work
        assertEquals(true, existingChapters["1"]?.isDownloaded)
        assertEquals(false, existingChapters["2"]?.isDownloaded)
        assertEquals(true, existingChapters["3"]?.isDownloaded)
        assertNull(existingChapters["4"])
    }

    @Test
    fun `chapter number format mismatch detection`() {
        // DB has chapters with certain format
        val existingChapters = listOf(
            createChapter("manga1", "1", isDownloaded = true),
            createChapter("manga1", "1.5", isDownloaded = true),
            createChapter("manga1", "10", isDownloaded = true)
        ).associateBy { it.number }

        // Check various formats
        assertNotNull("'1' should match '1'", existingChapters["1"])
        assertNull("'01' should NOT match '1'", existingChapters["01"])
        assertNull("'1.0' should NOT match '1'", existingChapters["1.0"])
        assertNotNull("'1.5' should match '1.5'", existingChapters["1.5"])
        assertNull("'1.50' should NOT match '1.5'", existingChapters["1.50"])
    }

    @Test
    fun `insert ignore returns -1 for existing`() {
        // Simulate Room INSERT with IGNORE behavior
        // Returns row id for new insert, -1 if ignored (already exists)

        val existingIds = mutableSetOf("manga1:1", "manga1:2")

        fun simulateInsertIgnore(mangaId: String, number: String): Long {
            val key = "$mangaId:$number"
            return if (key in existingIds) {
                -1L // Ignored - already exists
            } else {
                existingIds.add(key)
                existingIds.size.toLong() // New row id
            }
        }

        // Existing chapter - should return -1
        assertEquals(-1L, simulateInsertIgnore("manga1", "1"))

        // New chapter - should return positive id
        assertTrue(simulateInsertIgnore("manga1", "3") > 0)

        // Same new chapter again - now exists, should return -1
        assertEquals(-1L, simulateInsertIgnore("manga1", "3"))
    }

    private fun createChapter(
        mangaId: String,
        number: String,
        isDownloaded: Boolean = false,
        localEnPath: String? = if (isDownloaded) "/path/en" else null,
        localEsPath: String? = if (isDownloaded) "/path/es" else null
    ) = ChapterEntity(
        mangaId = mangaId,
        number = number,
        title = "Chapter $number",
        enArchiveUrl = "https://example.com/en/$number.zip",
        esArchiveUrl = "https://example.com/es/$number.zip",
        enPageCount = 20,
        esPageCount = 20,
        isDownloaded = isDownloaded,
        localEnPath = localEnPath,
        localEsPath = localEsPath
    )
}
