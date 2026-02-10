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
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class MangaRepository @Inject constructor(
    private val api: MangaApi,
    private val mangaDao: MangaDao,
    private val chapterDao: ChapterDao,
    private val client: OkHttpClient,
    private val context: Context
) {
    private val chaptersDir = File(context.filesDir, "chapters")

    fun getAllManga(): Flow<List<MangaEntity>> = mangaDao.getAllManga()

    fun getChaptersForManga(mangaId: String): Flow<List<ChapterEntity>> =
        chapterDao.getChaptersForManga(mangaId)

    fun getDownloadedChapters(mangaId: String): Flow<List<ChapterEntity>> =
        chapterDao.getDownloadedChapters(mangaId)

    suspend fun refreshMangaList(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val mangaList = api.getMangaList()
            val entities = mangaList.map { item ->
                MangaEntity(
                    id = item.id,
                    title = item.title,
                    coverUrl = "${BuildConfig.BASE_URL}/${item.cover}",
                    chapterCount = item.chapter_count
                )
            }
            mangaDao.insertMangaList(entities)
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun refreshChapters(mangaId: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val response = api.getMangaDetail(mangaId)
            val entities = response.chapters.mapNotNull { chapter ->
                val enLang = chapter.languages["en"] ?: return@mapNotNull null
                val esLang = chapter.languages["es"] ?: return@mapNotNull null

                ChapterEntity(
                    mangaId = mangaId,
                    number = chapter.number,
                    title = chapter.title,
                    enArchiveUrl = "${BuildConfig.BASE_URL}/${enLang.archive}",
                    esArchiveUrl = "${BuildConfig.BASE_URL}/${esLang.archive}",
                    enPageCount = enLang.page_count,
                    esPageCount = esLang.page_count
                )
            }
            chapterDao.insertChapters(entities)
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun downloadChapter(
        chapter: ChapterEntity,
        onProgress: (Float) -> Unit = {}
    ): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val chapterDir = File(chaptersDir, "${chapter.mangaId}/${chapter.number}")
            val enDir = File(chapterDir, "en")
            val esDir = File(chapterDir, "es")

            // Download EN
            onProgress(0f)
            downloadAndExtractZip(chapter.enArchiveUrl, enDir)
            onProgress(0.5f)

            // Download ES
            downloadAndExtractZip(chapter.esArchiveUrl, esDir)
            onProgress(1f)

            // Update database
            chapterDao.updateDownloadStatus(
                mangaId = chapter.mangaId,
                number = chapter.number,
                downloaded = true,
                enPath = enDir.absolutePath,
                esPath = esDir.absolutePath
            )

            Result.success(Unit)
        } catch (e: Exception) {
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

    fun getChapterPages(chapter: ChapterEntity): List<Pair<File, File>> {
        if (!chapter.isDownloaded) return emptyList()

        val enDir = File(chapter.localEnPath ?: return emptyList())
        val esDir = File(chapter.localEsPath ?: return emptyList())

        val enPages = enDir.listFiles()?.filter { it.isFile }?.sortedBy { it.name } ?: emptyList()
        val esPages = esDir.listFiles()?.filter { it.isFile }?.sortedBy { it.name } ?: emptyList()

        return enPages.zip(esPages)
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
