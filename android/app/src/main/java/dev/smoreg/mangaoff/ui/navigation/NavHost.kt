package dev.smoreg.mangaoff.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import dev.smoreg.mangaoff.ui.screens.chapters.ChapterListScreen
import dev.smoreg.mangaoff.ui.screens.mangalist.MangaListScreen
import dev.smoreg.mangaoff.ui.screens.reader.ReaderScreen

object Routes {
    const val MANGA_LIST = "manga_list"
    const val CHAPTERS = "chapters/{mangaId}"
    const val READER = "reader/{mangaId}/{chapterNumber}"

    fun chapters(mangaId: String) = "chapters/$mangaId"
    fun reader(mangaId: String, chapterNumber: String) = "reader/$mangaId/$chapterNumber"
}

@Composable
fun MangaNavHost() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = Routes.MANGA_LIST
    ) {
        composable(Routes.MANGA_LIST) {
            MangaListScreen(
                onMangaClick = { mangaId ->
                    navController.navigate(Routes.chapters(mangaId))
                }
            )
        }

        composable(
            route = Routes.CHAPTERS,
            arguments = listOf(navArgument("mangaId") { type = NavType.StringType })
        ) { backStackEntry ->
            val mangaId = backStackEntry.arguments?.getString("mangaId") ?: return@composable
            ChapterListScreen(
                mangaId = mangaId,
                onBackClick = { navController.popBackStack() },
                onChapterClick = { chapterNumber ->
                    navController.navigate(Routes.reader(mangaId, chapterNumber))
                }
            )
        }

        composable(
            route = Routes.READER,
            arguments = listOf(
                navArgument("mangaId") { type = NavType.StringType },
                navArgument("chapterNumber") { type = NavType.StringType }
            )
        ) { backStackEntry ->
            val mangaId = backStackEntry.arguments?.getString("mangaId") ?: return@composable
            val chapterNumber = backStackEntry.arguments?.getString("chapterNumber") ?: return@composable
            ReaderScreen(
                mangaId = mangaId,
                chapterNumber = chapterNumber,
                onBackClick = { navController.popBackStack() }
            )
        }
    }
}
