package dev.smoreg.mangaoff.data.api

import retrofit2.http.GET
import retrofit2.http.Path

data class MangaListItem(
    val id: String,
    val title: String,
    val cover: String,
    val chapter_count: Int
)

data class LanguageInfo(
    val archive: String,
    val page_count: Int
)

data class ChapterInfo(
    val number: String,
    val title: String,
    val languages: Map<String, LanguageInfo>
)

data class MangaInfo(
    val id: String,
    val title: String,
    val cover: String
)

data class MangaDetailResponse(
    val manga: MangaInfo,
    val chapters: List<ChapterInfo>
)

interface MangaApi {
    @GET("api/v1/manga")
    suspend fun getMangaList(): List<MangaListItem>

    @GET("api/v1/manga/{id}")
    suspend fun getMangaDetail(@Path("id") mangaId: String): MangaDetailResponse
}
