package dev.smoreg.mangaoff.ui.screens.reader

import androidx.compose.animation.*
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import java.io.File

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun ReaderScreen(
    mangaId: String,
    chapterNumber: String,
    onBackClick: () -> Unit,
    viewModel: ReaderViewModel = hiltViewModel()
) {
    val pages by viewModel.pages.collectAsState()
    var showControls by remember { mutableStateOf(true) }

    val scope = rememberCoroutineScope()
    val configuration = LocalConfiguration.current
    val density = LocalDensity.current

    LaunchedEffect(mangaId, chapterNumber) {
        viewModel.loadChapter(mangaId, chapterNumber)
    }

    // Pages are already aligned by server - pair by page number
    val bilingualPages = remember(pages) {
        viewModel.getBilingualPages(pages)
    }

    val pagerState = rememberPagerState(pageCount = { bilingualPages.size })

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        if (bilingualPages.isEmpty()) {
            CircularProgressIndicator(
                modifier = Modifier.align(Alignment.Center),
                color = Color.White
            )
        } else {
            // Main pager
            HorizontalPager(
                state = pagerState,
                modifier = Modifier.fillMaxSize()
            ) { index ->
                val page = bilingualPages[index]
                BilingualPage(
                    page = page,
                    onTap = { tapX ->
                        val screenWidth = configuration.screenWidthDp.toFloat()
                        when {
                            tapX < screenWidth / 3 -> {
                                // Left tap - previous page
                                scope.launch {
                                    if (pagerState.currentPage > 0) {
                                        pagerState.animateScrollToPage(pagerState.currentPage - 1)
                                    }
                                }
                            }
                            tapX > screenWidth * 2 / 3 -> {
                                // Right tap - next page
                                scope.launch {
                                    if (pagerState.currentPage < bilingualPages.size - 1) {
                                        pagerState.animateScrollToPage(pagerState.currentPage + 1)
                                    }
                                }
                            }
                            else -> {
                                // Center tap - toggle controls
                                showControls = !showControls
                            }
                        }
                    },
                    density = density.density
                )
            }

            // Top bar
            AnimatedVisibility(
                visible = showControls,
                enter = slideInVertically() + fadeIn(),
                exit = slideOutVertically() + fadeOut(),
                modifier = Modifier.align(Alignment.TopCenter)
            ) {
                TopAppBar(
                    title = {
                        val currentPage = bilingualPages.getOrNull(pagerState.currentPage)
                        val pageInfo = currentPage?.let {
                            "Ch.${chapterNumber} - ${it.pageNumber + 1}/${pages.size} (${it.language.uppercase()})"
                        } ?: "Chapter $chapterNumber"
                        Text(pageInfo)
                    },
                    navigationIcon = {
                        IconButton(onClick = onBackClick) {
                            Icon(
                                Icons.Filled.ArrowBack,
                                contentDescription = "Back",
                                tint = Color.White
                            )
                        }
                    },
                    actions = { },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.Black.copy(alpha = 0.7f),
                        titleContentColor = Color.White
                    )
                )
            }

            // Bottom indicator
            AnimatedVisibility(
                visible = showControls,
                enter = slideInVertically(initialOffsetY = { it }) + fadeIn(),
                exit = slideOutVertically(targetOffsetY = { it }) + fadeOut(),
                modifier = Modifier.align(Alignment.BottomCenter)
            ) {
                Surface(
                    color = Color.Black.copy(alpha = 0.7f),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        LinearProgressIndicator(
                            progress = if (bilingualPages.isEmpty()) 0f
                                else (pagerState.currentPage + 1f) / bilingualPages.size,
                            modifier = Modifier.fillMaxWidth(),
                            color = MaterialTheme.colorScheme.primary,
                            trackColor = Color.Gray
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "${pagerState.currentPage + 1} / ${bilingualPages.size}",
                            color = Color.White,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }
        }
    }

}

@Composable
fun BilingualPage(
    page: BilingualPageData,
    onTap: (Float) -> Unit,
    density: Float
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                detectTapGestures { offset ->
                    onTap(offset.x / density)
                }
            }
    ) {
        if (page.imageFile != null) {
            AsyncImage(
                model = page.imageFile,
                contentDescription = "Page ${page.pageNumber + 1} (${page.language})",
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Fit
            )
        } else {
            // Missing page placeholder
            Column(
                modifier = Modifier.align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "Page ${page.pageNumber + 1}",
                    color = Color.White,
                    style = MaterialTheme.typography.headlineMedium
                )
                Text(
                    text = "(${page.language.uppercase()} - Not available)",
                    color = Color.Gray,
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        }

        // Language indicator
        Surface(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(16.dp),
            color = if (page.language == "en") Color(0xFF4CAF50) else Color(0xFFFF9800),
            shape = MaterialTheme.shapes.small
        ) {
            Text(
                text = page.language.uppercase(),
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                color = Color.White,
                style = MaterialTheme.typography.labelMedium
            )
        }
    }
}

data class BilingualPageData(
    val pageNumber: Int,       // Original page number (0-indexed)
    val language: String,      // "en" or "es"
    val imageFile: File?       // null if page doesn't exist (due to offset)
)
