package dev.smoreg.mangaoff.di

import android.content.Context
import androidx.room.Room
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import dev.smoreg.mangaoff.BuildConfig
import dev.smoreg.mangaoff.data.api.MangaApi
import dev.smoreg.mangaoff.data.db.ChapterDao
import dev.smoreg.mangaoff.data.db.MangaDao
import dev.smoreg.mangaoff.data.db.MangaDatabase
import dev.smoreg.mangaoff.data.repository.MangaRepository
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideOkHttpClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .addInterceptor(
                HttpLoggingInterceptor().apply {
                    level = HttpLoggingInterceptor.Level.BASIC
                }
            )
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(client: OkHttpClient): Retrofit {
        return Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    @Provides
    @Singleton
    fun provideMangaApi(retrofit: Retrofit): MangaApi {
        return retrofit.create(MangaApi::class.java)
    }

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): MangaDatabase {
        return Room.databaseBuilder(
            context,
            MangaDatabase::class.java,
            "mangaoff.db"
        ).build()
    }

    @Provides
    fun provideMangaDao(database: MangaDatabase): MangaDao = database.mangaDao()

    @Provides
    fun provideChapterDao(database: MangaDatabase): ChapterDao = database.chapterDao()

    @Provides
    @Singleton
    fun provideMangaRepository(
        api: MangaApi,
        mangaDao: MangaDao,
        chapterDao: ChapterDao,
        client: OkHttpClient,
        @ApplicationContext context: Context
    ): MangaRepository {
        return MangaRepository(api, mangaDao, chapterDao, client, context)
    }
}
