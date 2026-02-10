package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"

	"github.com/smoreg/mangaoff-server/handlers"
)

func main() {
	port := flag.Int("port", 8080, "HTTP server port")
	dataDir := flag.String("data", "/opt/mangaoff/data", "Data directory path")
	flag.Parse()

	// Verify data directory exists
	if _, err := os.Stat(*dataDir); os.IsNotExist(err) {
		log.Printf("Warning: data directory does not exist: %s", *dataDir)
	}

	r := chi.NewRouter()

	// Middleware
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(middleware.RealIP)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Content-Type"},
		ExposedHeaders:   []string{"Content-Length"},
		AllowCredentials: false,
		MaxAge:           300,
	}))

	// Health check
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	// API routes
	mangaHandler := handlers.NewMangaHandler(*dataDir)

	r.Route("/api/v1", func(r chi.Router) {
		r.Get("/manga", mangaHandler.ListManga)
		r.Get("/manga/{id}", mangaHandler.GetManga)
	})

	addr := fmt.Sprintf(":%d", *port)
	log.Printf("Starting server on %s", addr)
	log.Printf("Data directory: %s", *dataDir)

	if err := http.ListenAndServe(addr, r); err != nil {
		log.Fatal(err)
	}
}
