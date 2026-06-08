package main

import (
	"database/sql"
	"encoding/xml"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	_ "github.com/lib/pq"
)

var db *sql.DB

// ── SOAP envelope ─────────────────────────────────────────────

type Envelope struct {
	XMLName xml.Name `xml:"Envelope"`
	Body    Body     `xml:"Body"`
}

type Body struct {
	Content []byte `xml:",innerxml"`
}

// ── XML response models ───────────────────────────────────────

type XMLUser struct {
	XMLName   xml.Name `xml:"User"`
	ID        int      `xml:"id"`
	Name      string   `xml:"name"`
	Email     string   `xml:"email"`
	CreatedAt string   `xml:"created_at"`
}

type XMLSong struct {
	XMLName         xml.Name `xml:"Song"`
	ID              int      `xml:"id"`
	Title           string   `xml:"title"`
	Artist          string   `xml:"artist"`
	Album           string   `xml:"album"`
	Year            int      `xml:"year"`
	Genre           string   `xml:"genre"`
	DurationSeconds int      `xml:"duration_seconds"`
	CreatedAt       string   `xml:"created_at"`
}

type XMLPlaylist struct {
	XMLName   xml.Name `xml:"Playlist"`
	ID        int      `xml:"id"`
	UserID    int      `xml:"user_id"`
	Name      string   `xml:"name"`
	CreatedAt string   `xml:"created_at"`
}

// ── Helpers ───────────────────────────────────────────────────

const songCols = `id, title, artist, COALESCE(album,''), COALESCE(year,0), COALESCE(genre,''), COALESCE(duration_seconds,0), created_at`

func wrap(body string) string {
	return `<?xml version="1.0" encoding="UTF-8"?>` +
		`<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">` +
		`<soap:Body>` + body + `</soap:Body>` +
		`</soap:Envelope>`
}

func fault(msg string) string {
	return wrap(fmt.Sprintf(`<soap:Fault><faultstring>%s</faultstring></soap:Fault>`, msg))
}

func fmtTime(t time.Time) string { return t.Format(time.RFC3339) }

// extractOp gets the local name of the first element, ignoring namespace prefix
func extractOp(content string) string {
	content = strings.TrimSpace(content)
	if len(content) < 2 || content[0] != '<' {
		return ""
	}
	end := strings.IndexAny(content[1:], " >/\n\r\t")
	if end < 0 {
		return ""
	}
	name := content[1 : end+1]
	if i := strings.Index(name, ":"); i >= 0 {
		name = name[i+1:]
	}
	return name
}

func getIntField(content, field string) int {
	open := "<" + field + ">"
	close := "</" + field + ">"
	i := strings.Index(content, open)
	j := strings.Index(content, close)
	if i < 0 || j < 0 {
		return 0
	}
	var v int
	fmt.Sscanf(content[i+len(open):j], "%d", &v)
	return v
}

func getStrField(content, field string) string {
	open := "<" + field + ">"
	close := "</" + field + ">"
	i := strings.Index(content, open)
	j := strings.Index(content, close)
	if i < 0 || j < 0 {
		return ""
	}
	return content[i+len(open) : j]
}

// ── Handlers ──────────────────────────────────────────────────

func listUsers() string {
	rows, err := db.Query(`SELECT id,name,email,created_at FROM users ORDER BY id`)
	if err != nil {
		return fault(err.Error())
	}
	defer rows.Close()
	var sb strings.Builder
	sb.WriteString("<ListUsersResponse><users>")
	for rows.Next() {
		var u XMLUser
		var t time.Time
		rows.Scan(&u.ID, &u.Name, &u.Email, &t)
		u.CreatedAt = fmtTime(t)
		b, _ := xml.Marshal(u)
		sb.Write(b)
	}
	sb.WriteString("</users></ListUsersResponse>")
	return wrap(sb.String())
}

func getUser(content string) string {
	id := getIntField(content, "id")
	var u XMLUser
	var t time.Time
	err := db.QueryRow(`SELECT id,name,email,created_at FROM users WHERE id=$1`, id).
		Scan(&u.ID, &u.Name, &u.Email, &t)
	if err != nil {
		return fault(err.Error())
	}
	u.CreatedAt = fmtTime(t)
	b, _ := xml.Marshal(u)
	return wrap("<GetUserResponse>" + string(b) + "</GetUserResponse>")
}

func createUser(content string) string {
	name := getStrField(content, "name")
	email := getStrField(content, "email")
	var u XMLUser
	var t time.Time
	err := db.QueryRow(`INSERT INTO users(name,email) VALUES($1,$2) RETURNING id,name,email,created_at`, name, email).
		Scan(&u.ID, &u.Name, &u.Email, &t)
	if err != nil {
		return fault(err.Error())
	}
	u.CreatedAt = fmtTime(t)
	b, _ := xml.Marshal(u)
	return wrap("<CreateUserResponse>" + string(b) + "</CreateUserResponse>")
}

func updateUser(content string) string {
	id := getIntField(content, "id")
	name := getStrField(content, "name")
	email := getStrField(content, "email")
	var u XMLUser
	var t time.Time
	err := db.QueryRow(`UPDATE users SET name=$1,email=$2 WHERE id=$3 RETURNING id,name,email,created_at`, name, email, id).
		Scan(&u.ID, &u.Name, &u.Email, &t)
	if err != nil {
		return fault(err.Error())
	}
	u.CreatedAt = fmtTime(t)
	b, _ := xml.Marshal(u)
	return wrap("<UpdateUserResponse>" + string(b) + "</UpdateUserResponse>")
}

func deleteUser(content string) string {
	id := getIntField(content, "id")
	db.Exec(`DELETE FROM users WHERE id=$1`, id)
	return wrap("<DeleteUserResponse><ok>true</ok></DeleteUserResponse>")
}

func listSongs() string {
	rows, err := db.Query(`SELECT ` + songCols + ` FROM songs ORDER BY id`)
	if err != nil {
		return fault(err.Error())
	}
	defer rows.Close()
	var sb strings.Builder
	sb.WriteString("<ListSongsResponse><songs>")
	for rows.Next() {
		var s XMLSong
		var t time.Time
		rows.Scan(&s.ID, &s.Title, &s.Artist, &s.Album, &s.Year, &s.Genre, &s.DurationSeconds, &t)
		s.CreatedAt = fmtTime(t)
		b, _ := xml.Marshal(s)
		sb.Write(b)
	}
	sb.WriteString("</songs></ListSongsResponse>")
	return wrap(sb.String())
}

func getSong(content string) string {
	id := getIntField(content, "id")
	var s XMLSong
	var t time.Time
	err := db.QueryRow(`SELECT `+songCols+` FROM songs WHERE id=$1`, id).
		Scan(&s.ID, &s.Title, &s.Artist, &s.Album, &s.Year, &s.Genre, &s.DurationSeconds, &t)
	if err != nil {
		return fault(err.Error())
	}
	s.CreatedAt = fmtTime(t)
	b, _ := xml.Marshal(s)
	return wrap("<GetSongResponse>" + string(b) + "</GetSongResponse>")
}

func createSong(content string) string {
	title := getStrField(content, "title")
	artist := getStrField(content, "artist")
	album := getStrField(content, "album")
	year := getIntField(content, "year")
	genre := getStrField(content, "genre")
	dur := getIntField(content, "duration_seconds")
	var s XMLSong
	var t time.Time
	err := db.QueryRow(`INSERT INTO songs(title,artist,album,year,genre,duration_seconds) VALUES($1,$2,$3,$4,$5,$6) RETURNING `+songCols,
		title, artist, album, year, genre, dur).
		Scan(&s.ID, &s.Title, &s.Artist, &s.Album, &s.Year, &s.Genre, &s.DurationSeconds, &t)
	if err != nil {
		return fault(err.Error())
	}
	s.CreatedAt = fmtTime(t)
	b, _ := xml.Marshal(s)
	return wrap("<CreateSongResponse>" + string(b) + "</CreateSongResponse>")
}

func deleteSong(content string) string {
	id := getIntField(content, "id")
	db.Exec(`DELETE FROM songs WHERE id=$1`, id)
	return wrap("<DeleteSongResponse><ok>true</ok></DeleteSongResponse>")
}

func listPlaylists() string {
	rows, err := db.Query(`SELECT id,user_id,name,created_at FROM playlists ORDER BY id`)
	if err != nil {
		return fault(err.Error())
	}
	defer rows.Close()
	var sb strings.Builder
	sb.WriteString("<ListPlaylistsResponse><playlists>")
	for rows.Next() {
		var p XMLPlaylist
		var t time.Time
		rows.Scan(&p.ID, &p.UserID, &p.Name, &t)
		p.CreatedAt = fmtTime(t)
		b, _ := xml.Marshal(p)
		sb.Write(b)
	}
	sb.WriteString("</playlists></ListPlaylistsResponse>")
	return wrap(sb.String())
}

func getPlaylist(content string) string {
	id := getIntField(content, "id")
	var p XMLPlaylist
	var t time.Time
	err := db.QueryRow(`SELECT id,user_id,name,created_at FROM playlists WHERE id=$1`, id).
		Scan(&p.ID, &p.UserID, &p.Name, &t)
	if err != nil {
		return fault(err.Error())
	}
	p.CreatedAt = fmtTime(t)
	b, _ := xml.Marshal(p)
	return wrap("<GetPlaylistResponse>" + string(b) + "</GetPlaylistResponse>")
}

func listPlaylistsByUser(content string) string {
	uid := getIntField(content, "user_id")
	rows, err := db.Query(`SELECT id,user_id,name,created_at FROM playlists WHERE user_id=$1 ORDER BY id`, uid)
	if err != nil {
		return fault(err.Error())
	}
	defer rows.Close()
	var sb strings.Builder
	sb.WriteString("<ListPlaylistsByUserResponse><playlists>")
	for rows.Next() {
		var p XMLPlaylist
		var t time.Time
		rows.Scan(&p.ID, &p.UserID, &p.Name, &t)
		p.CreatedAt = fmtTime(t)
		b, _ := xml.Marshal(p)
		sb.Write(b)
	}
	sb.WriteString("</playlists></ListPlaylistsByUserResponse>")
	return wrap(sb.String())
}

func createPlaylist(content string) string {
	uid := getIntField(content, "user_id")
	name := getStrField(content, "name")
	var p XMLPlaylist
	var t time.Time
	err := db.QueryRow(`INSERT INTO playlists(user_id,name) VALUES($1,$2) RETURNING id,user_id,name,created_at`, uid, name).
		Scan(&p.ID, &p.UserID, &p.Name, &t)
	if err != nil {
		return fault(err.Error())
	}
	p.CreatedAt = fmtTime(t)
	b, _ := xml.Marshal(p)
	return wrap("<CreatePlaylistResponse>" + string(b) + "</CreatePlaylistResponse>")
}

func deletePlaylist(content string) string {
	id := getIntField(content, "id")
	db.Exec(`DELETE FROM playlists WHERE id=$1`, id)
	return wrap("<DeletePlaylistResponse><ok>true</ok></DeletePlaylistResponse>")
}

func getPlaylistSongs(content string) string {
	pid := getIntField(content, "playlist_id")
	rows, err := db.Query(`SELECT s.`+songCols+` FROM songs s JOIN playlist_songs ps ON s.id=ps.song_id WHERE ps.playlist_id=$1 ORDER BY s.id`, pid)
	if err != nil {
		return fault(err.Error())
	}
	defer rows.Close()
	var sb strings.Builder
	sb.WriteString("<GetPlaylistSongsResponse><songs>")
	for rows.Next() {
		var s XMLSong
		var t time.Time
		rows.Scan(&s.ID, &s.Title, &s.Artist, &s.Album, &s.Year, &s.Genre, &s.DurationSeconds, &t)
		s.CreatedAt = fmtTime(t)
		b, _ := xml.Marshal(s)
		sb.Write(b)
	}
	sb.WriteString("</songs></GetPlaylistSongsResponse>")
	return wrap(sb.String())
}

func addSong(content string) string {
	pid := getIntField(content, "playlist_id")
	sid := getIntField(content, "song_id")
	db.Exec(`INSERT INTO playlist_songs(playlist_id,song_id) VALUES($1,$2) ON CONFLICT DO NOTHING`, pid, sid)
	return wrap("<AddSongToPlaylistResponse><ok>true</ok></AddSongToPlaylistResponse>")
}

func removeSong(content string) string {
	pid := getIntField(content, "playlist_id")
	sid := getIntField(content, "song_id")
	db.Exec(`DELETE FROM playlist_songs WHERE playlist_id=$1 AND song_id=$2`, pid, sid)
	return wrap("<RemoveSongFromPlaylistResponse><ok>true</ok></RemoveSongFromPlaylistResponse>")
}

// ── HTTP handler ──────────────────────────────────────────────

func soapHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(405)
		return
	}
	body, _ := io.ReadAll(r.Body)
	var env Envelope
	if err := xml.Unmarshal(body, &env); err != nil {
		w.Header().Set("Content-Type", "text/xml")
		fmt.Fprint(w, fault("invalid SOAP envelope"))
		return
	}
	content := strings.TrimSpace(string(env.Body.Content))
	op := extractOp(content)
	w.Header().Set("Content-Type", "text/xml; charset=utf-8")
	var resp string
	switch op {
	case "ListUsers":
		resp = listUsers()
	case "GetUser":
		resp = getUser(content)
	case "CreateUser":
		resp = createUser(content)
	case "UpdateUser":
		resp = updateUser(content)
	case "DeleteUser":
		resp = deleteUser(content)
	case "ListSongs":
		resp = listSongs()
	case "GetSong":
		resp = getSong(content)
	case "CreateSong":
		resp = createSong(content)
	case "DeleteSong":
		resp = deleteSong(content)
	case "ListPlaylists":
		resp = listPlaylists()
	case "GetPlaylist":
		resp = getPlaylist(content)
	case "ListPlaylistsByUser":
		resp = listPlaylistsByUser(content)
	case "CreatePlaylist":
		resp = createPlaylist(content)
	case "DeletePlaylist":
		resp = deletePlaylist(content)
	case "GetPlaylistSongs":
		resp = getPlaylistSongs(content)
	case "AddSongToPlaylist":
		resp = addSong(content)
	case "RemoveSongFromPlaylist":
		resp = removeSong(content)
	default:
		resp = fault("unknown operation: " + op)
	}
	fmt.Fprint(w, resp)
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

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"status":"ok"}`)
	})
	http.HandleFunc("/soap", soapHandler)
	http.HandleFunc("/", soapHandler) // SOAP clients may POST to /

	port := os.Getenv("PORT")
	if port == "" {
		port = "8004"
	}
	log.Printf("Go SOAP listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
