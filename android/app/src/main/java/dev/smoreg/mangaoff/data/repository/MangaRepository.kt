package dev.smoreg.mangaoff.data.repository

import android.content.Context
import dev.smoreg.mangaoff.BuildConfig
import dev.smoreg.mangaoff.data.api.MangaApi
import dev.smoreg.mangaoff.data.db.ChapterDao
import dev.smoreg.mangaoff.data.db.ChapterEntity
import dev.smoreg.mangaoff.data.db.MangaDao
import dev.smoreg.mangaoff.data.db.MangaEntity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import dev.smoreg.mangaoff.util.DebugLog as Log
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream
import javax.inject.Inject
import javax.inject.Singleton

private const val TAG = "MangaRepository"

@Singleton
class MangaRepository @Inject constructor(
    private val api: MangaApi,
    private val mangaDao: MangaDao,
    private val chapterDao: ChapterDao,
    private val client: OkHttpClient,
    private val context: Context
) {
    private val chaptersDir = File(context.filesDir, "chapters")

    /**
     * Verify downloaded chapters - restore DB status if files exist on disk
     * Call this on app startup to handle app updates or DB issues
     */
    suspend fun verifyDownloadedChapters(mangaId: String) = withContext(Dispatchers.IO) {
        Log.d(TAG, "verifyDownloadedChapters START for $mangaId")
        val chapters = chapterDao.getChaptersListForManga(mangaId)
        Log.d(TAG, "verifyDownloadedChapters: found ${chapters.size} chapters in DB")

        val downloadedInDb = chapters.count { it.isDownloaded }
        Log.d(TAG, "verifyDownloadedChapters: $downloadedInDb marked as downloaded in DB")

        val mangaDir = File(chaptersDir, mangaId)
        Log.d(TAG, "verifyDownloadedChapters: checking files in ${mangaDir.absolutePath}")
        Log.d(TAG, "verifyDownloadedChapters: mangaDir exists = ${mangaDir.exists()}")

        for (chapter in chapters) {
            val chapterDir = File(mangaDir, chapter.number)
            val enDir = File(chapterDir, "en")
            val esDir = File(chapterDir, "es")

            val enExists = enDir.exists() && (enDir.listFiles()?.isNotEmpty() == true)
            val esExists = esDir.exists() && (esDir.listFiles()?.isNotEmpty() == true)
            val filesExist = enExists && esExists

            if (filesExist && !chapter.isDownloaded) {
                Log.w(TAG, "RESTORE ch ${chapter.number}: files exist but DB says not downloaded")
                chapterDao.updateDownloadStatus(
                    mangaId = mangaId,
                    number = chapter.number,
                    downloaded = true,
                    enPath = enDir.absolutePath,
                    esPath = esDir.absolutePath
                )
            } else if (!filesExist && chapter.isDownloaded) {
                Log.w(TAG, "FIX ch ${chapter.number}: DB says downloaded but files missing")
                chapterDao.updateDownloadStatus(
                    mangaId = mangaId,
                    number = chapter.number,
                    downloaded = false,
                    enPath = null,
                    esPath = null
                )
            }
        }
        Log.d(TAG, "verifyDownloadedChapters END")
    }

    fun getAllManga(): Flow<List<MangaEntity>> = mangaDao.getAllManga()

    fun getChaptersForManga(mangaId: String): Flow<List<ChapterEntity>> =
        chapterDao.getChaptersForManga(mangaId)

    fun getDownloadedChapters(mangaId: String): Flow<List<ChapterEntity>> =
        chapterDao.getDownloadedChapters(mangaId)

    suspend fun refreshMangaList(): Result<Unit> = withContext(Dispatchers.IO) {
        Log.d(TAG, "refreshMangaList START")
        try {
            val mangaList = api.getMangaList()
            Log.d(TAG, "refreshMangaList: API returned ${mangaList.size} manga")

            for (item in mangaList) {
                val entity = MangaEntity(
                    id = item.id,
                    title = item.title,
                    coverUrl = "${BuildConfig.BASE_URL}/${item.cover}",
                    chapterCount = item.chapter_count
                )
                // Insert with IGNORE - won't touch existing
                mangaDao.insertMangaList(listOf(entity))
                // Update metadata for existing
                mangaDao.updateManga(
                    id = item.id,
                    title = item.title,
                    coverUrl = "${BuildConfig.BASE_URL}/${item.cover}",
                    chapterCount = item.chapter_count
                )
            }

            Log.d(TAG, "refreshMangaList END")
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "refreshMangaList ERROR: ${e.message}", e)
            Result.failure(e)
        }
    }

    suspend fun refreshChapters(mangaId: String): Result<Unit> = withContext(Dispatchers.IO) {
        Log.d(TAG, "refreshChapters START for $mangaId")
        try {
            val response = api.getMangaDetail(mangaId)
            Log.d(TAG, "refreshChapters: API returned ${response.chapters.size} chapters")

            var inserted = 0
            var updated = 0

            for (chapter in response.chapters) {
                val enLang = chapter.languages["en"] ?: continue
                val esLang = chapter.languages["es"] ?: continue

                val enArchiveUrl = "${BuildConfig.BASE_URL}/${enLang.archive}"
                val esArchiveUrl = "${BuildConfig.BASE_URL}/${esLang.archive}"

                // Try to insert new chapter (IGNORE if already exists)
                val result = chapterDao.insertChapter(
                    ChapterEntity(
                        mangaId = mangaId,
                        number = chapter.number,
                        title = chapter.title,
                        enArchiveUrl = enArchiveUrl,
                        esArchiveUrl = esArchiveUrl,
                        enPageCount = enLang.page_count,
                        esPageCount = esLang.page_count,
                        isDownloaded = false,
                        localEnPath = null,
                        localEsPath = null
                    )
                )

                // If insert was ignored (chapter exists), update metadata only
                if (result == -1L) {
                    chapterDao.updateChapterMetadata(
                        mangaId = mangaId,
                        number = chapter.number,
                        title = chapter.title,
                        enArchiveUrl = enArchiveUrl,
                        esArchiveUrl = esArchiveUrl,
                        enPageCount = enLang.page_count,
                        esPageCount = esLang.page_count
                    )
                    updated++
                } else {
                    inserted++
                }
            }

            Log.d(TAG, "refreshChapters END: inserted=$inserted, updated=$updated")
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "refreshChapters ERROR: ${e.message}", e)
            Result.failure(e)
        }
    }

    suspend fun downloadChapter(
        chapter: ChapterEntity,
        onProgress: (Float) -> Unit = {}
    ): Result<Unit> = withContext(Dispatchers.IO) {
        Log.d(TAG, "downloadChapter START: ${chapter.mangaId} ch ${chapter.number}")
        try {
            val chapterDir = File(chaptersDir, "${chapter.mangaId}/${chapter.number}")
            val enDir = File(chapterDir, "en")
            val esDir = File(chapterDir, "es")

            Log.d(TAG, "downloadChapter: saving to ${chapterDir.absolutePath}")

            // Download EN
            onProgress(0f)
            downloadAndExtractZip(chapter.enArchiveUrl, enDir)
            Log.d(TAG, "downloadChapter: EN done, files=${enDir.listFiles()?.size ?: 0}")
            onProgress(0.5f)

            // Download ES
            downloadAndExtractZip(chapter.esArchiveUrl, esDir)
            Log.d(TAG, "downloadChapter: ES done, files=${esDir.listFiles()?.size ?: 0}")
            onProgress(1f)

            // Update database
            Log.d(TAG, "downloadChapter: updating DB status to downloaded=true")
            chapterDao.updateDownloadStatus(
                mangaId = chapter.mangaId,
                number = chapter.number,
                downloaded = true,
                enPath = enDir.absolutePath,
                esPath = esDir.absolutePath
            )

            Log.d(TAG, "downloadChapter END: success")
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "downloadChapter ERROR: ${e.message}", e)
            Result.failure(e)
        }
    }

    private fun downloadAndExtractZip(url: String, destDir: File) {
        destDir.mkdirs()

        val request = Request.Builder().url(url).build()
        val response = client.newCall(request).execute()

        if (!response.isSuccessful) {
            throw Exception("Download failed: ${response.code}")
        }

        response.body?.byteStream()?.use { inputStream ->
            ZipInputStream(inputStream).use { zis ->
                var entry = zis.nextEntry
                while (entry != null) {
                    if (!entry.isDirectory) {
                        val file = File(destDir, entry.name)
                        file.parentFile?.mkdirs()
                        FileOutputStream(file).use { fos ->
                            zis.copyTo(fos)
                        }
                    }
                    zis.closeEntry()
                    entry = zis.nextEntry
                }
            }
        }
    }

    fun getChapterPages(chapter: ChapterEntity): List<Pair<File?, File?>> {
        if (!chapter.isDownloaded) return emptyList()

        val enDir = File(chapter.localEnPath ?: return emptyList())
        val esDir = File(chapter.localEsPath ?: return emptyList())

        // Build maps by page number (filename without extension)
        val enPages = enDir.listFiles()
            ?.filter { it.isFile }
            ?.associateBy { it.nameWithoutExtension }
            ?: emptyMap()

        val esPages = esDir.listFiles()
            ?.filter { it.isFile }
            ?.associateBy { it.nameWithoutExtension }
            ?: emptyMap()

        // Get all unique page numbers and sort
        val allPageNumbers = (enPages.keys + esPages.keys)
            .sortedBy { it.toIntOrNull() ?: Int.MAX_VALUE }

        // Pair by page number - pages with same number should match
        return allPageNumbers.map { pageNum ->
            Pair(enPages[pageNum], esPages[pageNum])
        }
    }

    suspend fun deleteChapter(chapter: ChapterEntity): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            // Delete EN files
            chapter.localEnPath?.let { path ->
                File(path).deleteRecursively()
            }

            // Delete ES files
            chapter.localEsPath?.let { path ->
                File(path).deleteRecursively()
            }

            // Delete parent chapter directory if empty
            val chapterDir = File(chaptersDir, "${chapter.mangaId}/${chapter.number}")
            if (chapterDir.exists() && chapterDir.listFiles()?.isEmpty() == true) {
                chapterDir.delete()
            }

            // Update database
            chapterDao.updateDownloadStatus(
                mangaId = chapter.mangaId,
                number = chapter.number,
                downloaded = false,
                enPath = null,
                esPath = null
            )

            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
