package dev.smoreg.mangaoff.data.db

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "manga")
data class MangaEntity(
    @PrimaryKey val id: String,
    val title: String,
    val coverUrl: String,
    val chapterCount: Int
)

@Entity(
    tableName = "chapters",
    primaryKeys = ["mangaId", "number"],
    foreignKeys = [ForeignKey(
        entity = MangaEntity::class,
        parentColumns = ["id"],
        childColumns = ["mangaId"],
        onDelete = ForeignKey.CASCADE
    )]
)
data class ChapterEntity(
    val mangaId: String,
    val number: String,
    val title: String,
    val enArchiveUrl: String,
    val esArchiveUrl: String,
    val enPageCount: Int,
    val esPageCount: Int,
    val isDownloaded: Boolean = false,
    val localEnPath: String? = null,
    val localEsPath: String? = null
)

@Dao
interface MangaDao {
    @Query("SELECT * FROM manga ORDER BY title")
    fun getAllManga(): Flow<List<MangaEntity>>

    @Query("SELECT * FROM manga WHERE id = :id")
    suspend fun getMangaById(id: String): MangaEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertManga(manga: MangaEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertMangaList(manga: List<MangaEntity>)

    @Query("DELETE FROM manga")
    suspend fun deleteAllManga()
}

@Dao
interface ChapterDao {
    @Query("SELECT * FROM chapters WHERE mangaId = :mangaId ORDER BY CAST(number AS REAL)")
    fun getChaptersForManga(mangaId: String): Flow<List<ChapterEntity>>

    @Query("SELECT * FROM chapters WHERE mangaId = :mangaId AND number = :number")
    suspend fun getChapter(mangaId: String, number: String): ChapterEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertChapters(chapters: List<ChapterEntity>)

    @Query("UPDATE chapters SET isDownloaded = :downloaded, localEnPath = :enPath, localEsPath = :esPath WHERE mangaId = :mangaId AND number = :number")
    suspend fun updateDownloadStatus(mangaId: String, number: String, downloaded: Boolean, enPath: String?, esPath: String?)

    @Query("SELECT * FROM chapters WHERE mangaId = :mangaId AND isDownloaded = 1 ORDER BY CAST(number AS REAL)")
    fun getDownloadedChapters(mangaId: String): Flow<List<ChapterEntity>>
}

@Database(entities = [MangaEntity::class, ChapterEntity::class], version = 1, exportSchema = false)
abstract class MangaDatabase : RoomDatabase() {
    abstract fun mangaDao(): MangaDao
    abstract fun chapterDao(): ChapterDao
}
