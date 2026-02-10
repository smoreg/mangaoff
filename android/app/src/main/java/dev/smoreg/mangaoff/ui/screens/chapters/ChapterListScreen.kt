package dev.smoreg.mangaoff.ui.screens.chapters

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.DownloadForOffline
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import dev.smoreg.mangaoff.data.db.ChapterEntity

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChapterListScreen(
    mangaId: String,
    onBackClick: () -> Unit,
    onChapterClick: (String) -> Unit,
    viewModel: ChapterListViewModel = hiltViewModel()
) {
    val chapters by viewModel.chapters.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val downloadProgress by viewModel.downloadProgress.collectAsState()
    val downloadingChapter by viewModel.downloadingChapter.collectAsState()
    val isDownloadingAll by viewModel.isDownloadingAll.collectAsState()
    val downloadAllProgress by viewModel.downloadAllProgress.collectAsState()

    val notDownloadedCount = chapters.count { !it.isDownloaded }
    val downloadedCount = chapters.count { it.isDownloaded }

    var chapterToDelete by remember { mutableStateOf<ChapterEntity?>(null) }

    LaunchedEffect(mangaId) {
        viewModel.loadChapters(mangaId)
    }

    // Delete confirmation dialog
    chapterToDelete?.let { chapter ->
        AlertDialog(
            onDismissRequest = { chapterToDelete = null },
            title = { Text("Delete Chapter ${chapter.number}?") },
            text = {
                Text("This will delete both EN and ES versions from your device. You can download them again later.")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.deleteChapter(chapter)
                        chapterToDelete = null
                    },
                    colors = ButtonDefaults.textButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    )
                ) {
                    Text("Delete")
                }
            },
            dismissButton = {
                TextButton(onClick = { chapterToDelete = null }) {
                    Text("Cancel")
                }
            }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Chapters")
                        if (isDownloadingAll) {
                            Text(
                                text = "Downloading... ${(downloadAllProgress * 100).toInt()}%",
                                style = MaterialTheme.typography.bodySmall
                            )
                        } else if (chapters.isNotEmpty()) {
                            Text(
                                text = "$downloadedCount/${chapters.size} downloaded",
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    if (isDownloadingAll) {
                        IconButton(onClick = { viewModel.cancelDownloadAll() }) {
                            Icon(Icons.Default.Close, contentDescription = "Cancel")
                        }
                    } else if (notDownloadedCount > 0) {
                        IconButton(onClick = { viewModel.downloadAllChapters() }) {
                            Icon(Icons.Default.DownloadForOffline, contentDescription = "Download All")
                        }
                    }
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                }
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            if (chapters.isEmpty() && !isLoading) {
                Text(
                    text = "No chapters available",
                    modifier = Modifier.align(Alignment.Center),
                    style = MaterialTheme.typography.bodyLarge
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(chapters, key = { it.number }) { chapter ->
                        ChapterListItem(
                            chapter = chapter,
                            isDownloading = downloadingChapter == chapter.number,
                            downloadProgress = if (downloadingChapter == chapter.number) downloadProgress else null,
                            onDownloadClick = { viewModel.downloadChapter(chapter) },
                            onDeleteClick = { chapterToDelete = chapter },
                            onChapterClick = {
                                if (chapter.isDownloaded) {
                                    onChapterClick(chapter.number)
                                }
                            }
                        )
                    }
                }
            }

            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center)
                )
            }
        }
    }
}

@Composable
fun ChapterListItem(
    chapter: ChapterEntity,
    isDownloading: Boolean,
    downloadProgress: Float?,
    onDownloadClick: () -> Unit,
    onDeleteClick: () -> Unit,
    onChapterClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(
                enabled = chapter.isDownloaded && !isDownloading,
                onClick = onChapterClick
            ),
        colors = CardDefaults.cardColors(
            containerColor = if (chapter.isDownloaded)
                MaterialTheme.colorScheme.primaryContainer
            else
                MaterialTheme.colorScheme.surface
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Chapter ${chapter.number}",
                    style = MaterialTheme.typography.titleMedium
                )
                if (chapter.title.isNotBlank()) {
                    Text(
                        text = chapter.title,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Text(
                    text = "EN: ${chapter.enPageCount} pages | ES: ${chapter.esPageCount} pages",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(modifier = Modifier.width(8.dp))

            when {
                isDownloading -> {
                    Box(contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(
                            progress = downloadProgress ?: 0f,
                            modifier = Modifier.size(40.dp),
                            strokeWidth = 3.dp
                        )
                        Text(
                            text = "${((downloadProgress ?: 0f) * 100).toInt()}%",
                            style = MaterialTheme.typography.labelSmall
                        )
                    }
                }
                chapter.isDownloaded -> {
                    Row {
                        Icon(
                            Icons.Default.Check,
                            contentDescription = "Downloaded",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        IconButton(
                            onClick = onDeleteClick,
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(
                                Icons.Default.Delete,
                                contentDescription = "Delete",
                                tint = MaterialTheme.colorScheme.error,
                                modifier = Modifier.size(24.dp)
                            )
                        }
                    }
                }
                else -> {
                    IconButton(onClick = onDownloadClick) {
                        Icon(
                            Icons.Default.Download,
                            contentDescription = "Download",
                            modifier = Modifier.size(32.dp)
                        )
                    }
                }
            }
        }
    }
}
