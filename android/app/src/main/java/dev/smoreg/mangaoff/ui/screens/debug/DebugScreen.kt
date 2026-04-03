package dev.smoreg.mangaoff.ui.screens.debug

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.smoreg.mangaoff.util.DebugLog

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DebugScreen(
    onBackClick: () -> Unit
) {
    val logs by DebugLog.logs.collectAsState()
    val listState = rememberLazyListState()
    val context = LocalContext.current

    // Auto-scroll to bottom when new logs arrive
    LaunchedEffect(logs.size) {
        if (logs.isNotEmpty()) {
            listState.animateScrollToItem(logs.size - 1)
        }
    }

    fun shareLogs() {
        val text = logs.joinToString("\n")
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, "MangaOff Debug Logs")
            putExtra(Intent.EXTRA_TEXT, text)
        }
        context.startActivity(Intent.createChooser(intent, "Share logs"))
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Debug Logs (${logs.size})") },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { shareLogs() }, enabled = logs.isNotEmpty()) {
                        Icon(Icons.Default.Share, contentDescription = "Share")
                    }
                    IconButton(onClick = { DebugLog.clear() }) {
                        Icon(Icons.Default.Delete, contentDescription = "Clear")
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color.Black),
            contentPadding = PaddingValues(8.dp)
        ) {
            items(logs) { log ->
                val color = when {
                    log.contains(" E/") -> Color(0xFFFF6B6B)
                    log.contains(" W/") -> Color(0xFFFFE066)
                    else -> Color(0xFF90EE90)
                }
                Text(
                    text = log,
                    color = color,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .padding(vertical = 2.dp)
                )
            }

            if (logs.isEmpty()) {
                item {
                    Text(
                        text = "No logs yet. Go to chapter list to see logs.",
                        color = Color.Gray,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(16.dp)
                    )
                }
            }
        }
    }
}
