package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	_ "github.com/lib/pq"
)

var db *sql.DB

// ── Models ────────────────────────────────────────────────────

type User struct {
	ID        int    `json:"id"`
	Name      string `json:"name"`
	Email     string `json:"email"`
	CreatedAt string `json:"created_at"`
}

type Song struct {
	ID              int    `json:"id"`
	Title           string `json:"title"`
	Artist          string `json:"artist"`
	Album           string `json:"album"`
	Year            int    `json:"year"`
	Genre           string `json:"genre"`
	DurationSeconds int    `json:"duration_seconds"`
	CreatedAt       string `json:"created_at"`
}

type Playlist struct {
	ID        int    `json:"id"`
	UserID    int    `json:"user_id"`
	Name      string `json:"name"`
	CreatedAt string `json:"created_at"`
}

// ── Main ──────────────────────────────────────────────────────

func main() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "postgres://music:music123@localhost:5432/musicdb?sslmode=disable"
	}

	var err error
	for i := 0; i < 30; i++ {
		db, err = sql.Open("postgres", dsn)
		if err == nil {
			if err = db.Ping(); err == nil {
				break
			}
			db.Close()
		}
		log.Printf("Waiting for DB (%d/30)…", i+1)
		time.Sleep(2 * time.Second)
	}
	if err != nil {
		log.Fatalf("DB unreachable: %v", err)
	}
	defer db.Close()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"status":"ok"}`)
	})
	mux.HandleFunc("/users", usersHandler)
	mux.HandleFunc("/users/", userHandler)
	mux.HandleFunc("/songs", songsHandler)
	mux.HandleFunc("/songs/", songHandler)
	mux.HandleFunc("/playlists", playlistsHandler)
	mux.HandleFunc("/playlists/", playlistHandler)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8001"
	}
	log.Printf("Go REST listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

// ── Helpers ───────────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

func fmtTime(t time.Time) string { return t.Format(time.RFC3339) }

const songCols = `id, title, artist, COALESCE(album,''), COALESCE(year,0), COALESCE(genre,''), COALESCE(duration_seconds,0), created_at`

func scanSong(row *sql.Row) (Song, error) {
	var s Song
	var t time.Time
	err := row.Scan(&s.ID, &s.Title, &s.Artist, &s.Album, &s.Year, &s.Genre, &s.DurationSeconds, &t)
	s.CreatedAt = fmtTime(t)
	return s, err
}

// ── Users ─────────────────────────────────────────────────────

func usersHandler(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		rows, err := db.Query(`SELECT id, name, email, created_at FROM users ORDER BY id`)
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		defer rows.Close()
		users := []User{}
		for rows.Next() {
			var u User
			var t time.Time
			rows.Scan(&u.ID, &u.Name, &u.Email, &t)
			u.CreatedAt = fmtTime(t)
			users = append(users, u)
		}
		writeJSON(w, 200, users)

	case http.MethodPost:
		var b struct {
			Name  string `json:"name"`
			Email string `json:"email"`
		}
		if json.NewDecoder(r.Body).Decode(&b) != nil {
			writeError(w, 400, "invalid body")
			return
		}
		var u User
		var t time.Time
		err := db.QueryRow(`INSERT INTO users(name,email) VALUES($1,$2) RETURNING id,name,email,created_at`,
			b.Name, b.Email).Scan(&u.ID, &u.Name, &u.Email, &t)
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		u.CreatedAt = fmtTime(t)
		writeJSON(w, 201, u)

	default:
		writeError(w, 405, "method not allowed")
	}
}

func userHandler(w http.ResponseWriter, r *http.Request) {
	idStr := strings.TrimPrefix(r.URL.Path, "/users/")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		writeError(w, 400, "invalid id")
		return
	}

	switch r.Method {
	case http.MethodGet:
		var u User
		var t time.Time
		err := db.QueryRow(`SELECT id,name,email,created_at FROM users WHERE id=$1`, id).
			Scan(&u.ID, &u.Name, &u.Email, &t)
		if err == sql.ErrNoRows {
			writeError(w, 404, "user not found")
			return
		}
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		u.CreatedAt = fmtTime(t)
		writeJSON(w, 200, u)

	case http.MethodPut:
		var b struct {
			Name  string `json:"name"`
			Email string `json:"email"`
		}
		json.NewDecoder(r.Body).Decode(&b)
		var u User
		var t time.Time
		err := db.QueryRow(`UPDATE users SET name=COALESCE(NULLIF($1,''),name),email=COALESCE(NULLIF($2,''),email) WHERE id=$3 RETURNING id,name,email,created_at`,
			b.Name, b.Email, id).Scan(&u.ID, &u.Name, &u.Email, &t)
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		u.CreatedAt = fmtTime(t)
		writeJSON(w, 200, u)

	case http.MethodDelete:
		db.Exec(`DELETE FROM users WHERE id=$1`, id)
		w.WriteHeader(204)

	default:
		writeError(w, 405, "method not allowed")
	}
}

// ── Songs ─────────────────────────────────────────────────────

func songsHandler(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		rows, err := db.Query(`SELECT ` + songCols + ` FROM songs ORDER BY id`)
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		defer rows.Close()
		songs := []Song{}
		for rows.Next() {
			var s Song
			var t time.Time
			rows.Scan(&s.ID, &s.Title, &s.Artist, &s.Album, &s.Year, &s.Genre, &s.DurationSeconds, &t)
			s.CreatedAt = fmtTime(t)
			songs = append(songs, s)
		}
		writeJSON(w, 200, songs)

	case http.MethodPost:
		var s Song
		json.NewDecoder(r.Body).Decode(&s)
		result, err := scanSong(db.QueryRow(
			`INSERT INTO songs(title,artist,album,year,genre,duration_seconds) VALUES($1,$2,$3,$4,$5,$6) RETURNING `+songCols,
			s.Title, s.Artist, s.Album, s.Year, s.Genre, s.DurationSeconds))
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		writeJSON(w, 201, result)

	default:
		writeError(w, 405, "method not allowed")
	}
}

func songHandler(w http.ResponseWriter, r *http.Request) {
	idStr := strings.TrimPrefix(r.URL.Path, "/songs/")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		writeError(w, 400, "invalid id")
		return
	}

	switch r.Method {
	case http.MethodGet:
		s, err := scanSong(db.QueryRow(`SELECT `+songCols+` FROM songs WHERE id=$1`, id))
		if err == sql.ErrNoRows {
			writeError(w, 404, "song not found")
			return
		}
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		writeJSON(w, 200, s)

	case http.MethodPut:
		var s Song
		json.NewDecoder(r.Body).Decode(&s)
		result, err := scanSong(db.QueryRow(
			`UPDATE songs SET title=$1,artist=$2,album=$3,year=$4,genre=$5,duration_seconds=$6 WHERE id=$7 RETURNING `+songCols,
			s.Title, s.Artist, s.Album, s.Year, s.Genre, s.DurationSeconds, id))
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		writeJSON(w, 200, result)

	case http.MethodDelete:
		db.Exec(`DELETE FROM songs WHERE id=$1`, id)
		w.WriteHeader(204)

	default:
		writeError(w, 405, "method not allowed")
	}
}

// ── Playlists ─────────────────────────────────────────────────

func playlistsHandler(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		playlists := []Playlist{}
		uidStr := r.URL.Query().Get("user_id")
		var rows *sql.Rows
		var err error
		if uidStr != "" {
			uid, _ := strconv.Atoi(uidStr)
			rows, err = db.Query(`SELECT id,user_id,name,created_at FROM playlists WHERE user_id=$1 ORDER BY id`, uid)
		} else {
			rows, err = db.Query(`SELECT id,user_id,name,created_at FROM playlists ORDER BY id`)
		}
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		defer rows.Close()
		for rows.Next() {
			var p Playlist
			var t time.Time
			rows.Scan(&p.ID, &p.UserID, &p.Name, &t)
			p.CreatedAt = fmtTime(t)
			playlists = append(playlists, p)
		}
		writeJSON(w, 200, playlists)

	case http.MethodPost:
		var b Playlist
		json.NewDecoder(r.Body).Decode(&b)
		var p Playlist
		var t time.Time
		err := db.QueryRow(`INSERT INTO playlists(user_id,name) VALUES($1,$2) RETURNING id,user_id,name,created_at`,
			b.UserID, b.Name).Scan(&p.ID, &p.UserID, &p.Name, &t)
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		p.CreatedAt = fmtTime(t)
		writeJSON(w, 201, p)

	default:
		writeError(w, 405, "method not allowed")
	}
}

func playlistHandler(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/playlists/")
	parts := strings.SplitN(path, "/", 2)
	id, err := strconv.Atoi(parts[0])
	if err != nil {
		writeError(w, 400, "invalid id")
		return
	}

	// /playlists/{id}/songs
	if len(parts) == 2 && parts[1] == "songs" {
		switch r.Method {
		case http.MethodGet:
			rows, err := db.Query(`SELECT s.`+songCols+` FROM songs s JOIN playlist_songs ps ON s.id=ps.song_id WHERE ps.playlist_id=$1 ORDER BY s.id`, id)
			if err != nil {
				writeError(w, 500, err.Error())
				return
			}
			defer rows.Close()
			songs := []Song{}
			for rows.Next() {
				var s Song
				var t time.Time
				rows.Scan(&s.ID, &s.Title, &s.Artist, &s.Album, &s.Year, &s.Genre, &s.DurationSeconds, &t)
				s.CreatedAt = fmtTime(t)
				songs = append(songs, s)
			}
			writeJSON(w, 200, songs)
		case http.MethodPost:
			var b struct{ SongID int `json:"song_id"` }
			json.NewDecoder(r.Body).Decode(&b)
			db.Exec(`INSERT INTO playlist_songs(playlist_id,song_id) VALUES($1,$2) ON CONFLICT DO NOTHING`, id, b.SongID)
			w.WriteHeader(201)
		case http.MethodDelete:
			var b struct{ SongID int `json:"song_id"` }
			json.NewDecoder(r.Body).Decode(&b)
			db.Exec(`DELETE FROM playlist_songs WHERE playlist_id=$1 AND song_id=$2`, id, b.SongID)
			w.WriteHeader(204)
		}
		return
	}

	switch r.Method {
	case http.MethodGet:
		var p Playlist
		var t time.Time
		err := db.QueryRow(`SELECT id,user_id,name,created_at FROM playlists WHERE id=$1`, id).
			Scan(&p.ID, &p.UserID, &p.Name, &t)
		if err == sql.ErrNoRows {
			writeError(w, 404, "playlist not found")
			return
		}
		if err != nil {
			writeError(w, 500, err.Error())
			return
		}
		p.CreatedAt = fmtTime(t)
		writeJSON(w, 200, p)

	case http.MethodPut:
		var b struct{ Name string `json:"name"` }
		json.NewDecoder(r.Body).Decode(&b)
		var p Playlist
		var t time.Time
		db.QueryRow(`UPDATE playlists SET name=$1 WHERE id=$2 RETURNING id,user_id,name,created_at`,
			b.Name, id).Scan(&p.ID, &p.UserID, &p.Name, &t)
		p.CreatedAt = fmtTime(t)
		writeJSON(w, 200, p)

	case http.MethodDelete:
		db.Exec(`DELETE FROM playlists WHERE id=$1`, id)
		w.WriteHeader(204)

	default:
		writeError(w, 405, "method not allowed")
	}
}
