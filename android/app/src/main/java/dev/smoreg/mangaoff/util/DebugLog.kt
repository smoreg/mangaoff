package dev.smoreg.mangaoff.util

import android.util.Log
import dev.smoreg.mangaoff.BuildConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.text.SimpleDateFormat
import java.util.*

object DebugLog {
    private val _logs = MutableStateFlow<List<String>>(emptyList())
    val logs: StateFlow<List<String>> = _logs.asStateFlow()

    private val timeFormat = SimpleDateFormat("HH:mm:ss.SSS", Locale.US)
    private const val MAX_LOGS = 200

    // Only collect in-app logs in debug builds
    private val enabled = BuildConfig.DEBUG

    fun d(tag: String, message: String) {
        Log.d(tag, message)
        if (enabled) add("D", tag, message)
    }

    fun w(tag: String, message: String) {
        Log.w(tag, message)
        if (enabled) add("W", tag, message)
    }

    fun e(tag: String, message: String, throwable: Throwable? = null) {
        Log.e(tag, message, throwable)
        if (enabled) add("E", tag, if (throwable != null) "$message: ${throwable.message}" else message)
    }

    private fun add(level: String, tag: String, message: String) {
        val time = timeFormat.format(Date())
        val entry = "$time $level/$tag: $message"
        _logs.value = (_logs.value + entry).takeLast(MAX_LOGS)
    }

    fun clear() {
        _logs.value = emptyList()
    }
}
