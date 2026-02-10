package handlers

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"

	"github.com/go-chi/chi/v5"
)

type MangaHandler struct {
	DataDir string
}

type MangaListItem struct {
	ID           string `json:"id"`
	Title        string `json:"title"`
	Cover        string `json:"cover"`
	ChapterCount int    `json:"chapter_count"`
}

type MangaInfo struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Cover string `json:"cover"`
}

type LanguageInfo struct {
	Archive   string `json:"archive"`
	PageCount int    `json:"page_count"`
}

type Chapter struct {
	Number    string                  `json:"number"`
	Title     string                  `json:"title"`
	Languages map[string]LanguageInfo `json:"languages"`
}

type Manifest struct {
	Version  int       `json:"version"`
	Manga    MangaInfo `json:"manga"`
	Chapters []Chapter `json:"chapters"`
}

type MangaDetailResponse struct {
	Manga    MangaInfo `json:"manga"`
	Chapters []Chapter `json:"chapters"`
}

func NewMangaHandler(dataDir string) *MangaHandler {
	return &MangaHandler{DataDir: dataDir}
}

// ListManga returns all available manga
func (h *MangaHandler) ListManga(w http.ResponseWriter, r *http.Request) {
	var mangaList []MangaListItem

	// Scan data directory for manga folders with manifest.json
	entries, err := os.ReadDir(h.DataDir)
	if err != nil {
		http.Error(w, "Failed to read data directory", http.StatusInternalServerError)
		return
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}

		manifestPath := filepath.Join(h.DataDir, entry.Name(), "manifest.json")
		manifest, err := loadManifest(manifestPath)
		if err != nil {
			continue
		}

		mangaList = append(mangaList, MangaListItem{
			ID:           manifest.Manga.ID,
			Title:        manifest.Manga.Title,
			Cover:        manifest.Manga.Cover,
			ChapterCount: len(manifest.Chapters),
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(mangaList)
}

// GetManga returns manga details with chapters
func (h *MangaHandler) GetManga(w http.ResponseWriter, r *http.Request) {
	mangaID := chi.URLParam(r, "id")
	if mangaID == "" {
		http.Error(w, "Manga ID required", http.StatusBadRequest)
		return
	}

	manifestPath := filepath.Join(h.DataDir, mangaID, "manifest.json")
	manifest, err := loadManifest(manifestPath)
	if err != nil {
		http.Error(w, "Manga not found", http.StatusNotFound)
		return
	}

	response := MangaDetailResponse{
		Manga:    manifest.Manga,
		Chapters: manifest.Chapters,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func loadManifest(path string) (*Manifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var manifest Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return nil, err
	}

	return &manifest, nil
}
