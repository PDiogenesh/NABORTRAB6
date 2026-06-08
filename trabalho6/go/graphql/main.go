package main

import (
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/graphql-go/graphql"
	_ "github.com/lib/pq"
)

var db *sql.DB

// ── GraphQL types ─────────────────────────────────────────────

var userType = graphql.NewObject(graphql.ObjectConfig{
	Name: "User",
	Fields: graphql.Fields{
		"id":         &graphql.Field{Type: graphql.Int},
		"name":       &graphql.Field{Type: graphql.String},
		"email":      &graphql.Field{Type: graphql.String},
		"created_at": &graphql.Field{Type: graphql.String},
	},
})

var songType = graphql.NewObject(graphql.ObjectConfig{
	Name: "Song",
	Fields: graphql.Fields{
		"id":               &graphql.Field{Type: graphql.Int},
		"title":            &graphql.Field{Type: graphql.String},
		"artist":           &graphql.Field{Type: graphql.String},
		"album":            &graphql.Field{Type: graphql.String},
		"year":             &graphql.Field{Type: graphql.Int},
		"genre":            &graphql.Field{Type: graphql.String},
		"duration_seconds": &graphql.Field{Type: graphql.Int},
		"created_at":       &graphql.Field{Type: graphql.String},
	},
})

var playlistType = graphql.NewObject(graphql.ObjectConfig{
	Name: "Playlist",
	Fields: graphql.Fields{
		"id":         &graphql.Field{Type: graphql.Int},
		"user_id":    &graphql.Field{Type: graphql.Int},
		"name":       &graphql.Field{Type: graphql.String},
		"created_at": &graphql.Field{Type: graphql.String},
	},
})

// ── Helpers ───────────────────────────────────────────────────

const songCols = `id, title, artist, COALESCE(album,''), COALESCE(year,0), COALESCE(genre,''), COALESCE(duration_seconds,0), created_at`

func rowToUser(id int, name, email string, t time.Time) map[string]interface{} {
	return map[string]interface{}{"id": id, "name": name, "email": email, "created_at": t.Format(time.RFC3339)}
}

func rowToSong(id int, title, artist, album string, year int, genre string, dur int, t time.Time) map[string]interface{} {
	return map[string]interface{}{
		"id": id, "title": title, "artist": artist, "album": album,
		"year": year, "genre": genre, "duration_seconds": dur,
		"created_at": t.Format(time.RFC3339),
	}
}

func rowToPlaylist(id, uid int, name string, t time.Time) map[string]interface{} {
	return map[string]interface{}{"id": id, "user_id": uid, "name": name, "created_at": t.Format(time.RFC3339)}
}

// ── Schema ────────────────────────────────────────────────────

var schema graphql.Schema

func buildSchema() {
	rootQuery := graphql.NewObject(graphql.ObjectConfig{
		Name: "Query",
		Fields: graphql.Fields{
			// Users
			"users": &graphql.Field{
				Type: graphql.NewList(userType),
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					rows, err := db.Query(`SELECT id,name,email,created_at FROM users ORDER BY id`)
					if err != nil {
						return nil, err
					}
					defer rows.Close()
					var list []map[string]interface{}
					for rows.Next() {
						var id int
						var name, email string
						var t time.Time
						rows.Scan(&id, &name, &email, &t)
						list = append(list, rowToUser(id, name, email, t))
					}
					return list, nil
				},
			},
			"user": &graphql.Field{
				Type: userType,
				Args: graphql.FieldConfigArgument{
					"id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					id := p.Args["id"].(int)
					var uid int
					var name, email string
					var t time.Time
					err := db.QueryRow(`SELECT id,name,email,created_at FROM users WHERE id=$1`, id).
						Scan(&uid, &name, &email, &t)
					if err != nil {
						return nil, err
					}
					return rowToUser(uid, name, email, t), nil
				},
			},
			// Songs
			"songs": &graphql.Field{
				Type: graphql.NewList(songType),
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					rows, err := db.Query(`SELECT ` + songCols + ` FROM songs ORDER BY id`)
					if err != nil {
						return nil, err
					}
					defer rows.Close()
					var list []map[string]interface{}
					for rows.Next() {
						var id, year, dur int
						var title, artist, album, genre string
						var t time.Time
						rows.Scan(&id, &title, &artist, &album, &year, &genre, &dur, &t)
						list = append(list, rowToSong(id, title, artist, album, year, genre, dur, t))
					}
					return list, nil
				},
			},
			"song": &graphql.Field{
				Type: songType,
				Args: graphql.FieldConfigArgument{
					"id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					id := p.Args["id"].(int)
					var sid, year, dur int
					var title, artist, album, genre string
					var t time.Time
					err := db.QueryRow(`SELECT `+songCols+` FROM songs WHERE id=$1`, id).
						Scan(&sid, &title, &artist, &album, &year, &genre, &dur, &t)
					if err != nil {
						return nil, err
					}
					return rowToSong(sid, title, artist, album, year, genre, dur, t), nil
				},
			},
			// Playlists
			"playlists": &graphql.Field{
				Type: graphql.NewList(playlistType),
				Args: graphql.FieldConfigArgument{
					"user_id": &graphql.ArgumentConfig{Type: graphql.Int},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					var rows *sql.Rows
					var err error
					if uid, ok := p.Args["user_id"].(int); ok && uid > 0 {
						rows, err = db.Query(`SELECT id,user_id,name,created_at FROM playlists WHERE user_id=$1 ORDER BY id`, uid)
					} else {
						rows, err = db.Query(`SELECT id,user_id,name,created_at FROM playlists ORDER BY id`)
					}
					if err != nil {
						return nil, err
					}
					defer rows.Close()
					var list []map[string]interface{}
					for rows.Next() {
						var id, uid int
						var name string
						var t time.Time
						rows.Scan(&id, &uid, &name, &t)
						list = append(list, rowToPlaylist(id, uid, name, t))
					}
					return list, nil
				},
			},
			"playlist": &graphql.Field{
				Type: playlistType,
				Args: graphql.FieldConfigArgument{
					"id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					id := p.Args["id"].(int)
					var pid, uid int
					var name string
					var t time.Time
					err := db.QueryRow(`SELECT id,user_id,name,created_at FROM playlists WHERE id=$1`, id).
						Scan(&pid, &uid, &name, &t)
					if err != nil {
						return nil, err
					}
					return rowToPlaylist(pid, uid, name, t), nil
				},
			},
			"playlist_songs": &graphql.Field{
				Type: graphql.NewList(songType),
				Args: graphql.FieldConfigArgument{
					"playlist_id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					pid := p.Args["playlist_id"].(int)
					rows, err := db.Query(`SELECT s.`+songCols+` FROM songs s JOIN playlist_songs ps ON s.id=ps.song_id WHERE ps.playlist_id=$1 ORDER BY s.id`, pid)
					if err != nil {
						return nil, err
					}
					defer rows.Close()
					var list []map[string]interface{}
					for rows.Next() {
						var id, year, dur int
						var title, artist, album, genre string
						var t time.Time
						rows.Scan(&id, &title, &artist, &album, &year, &genre, &dur, &t)
						list = append(list, rowToSong(id, title, artist, album, year, genre, dur, t))
					}
					return list, nil
				},
			},
		},
	})

	rootMutation := graphql.NewObject(graphql.ObjectConfig{
		Name: "Mutation",
		Fields: graphql.Fields{
			// User mutations
			"create_user": &graphql.Field{
				Type: userType,
				Args: graphql.FieldConfigArgument{
					"name":  &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.String)},
					"email": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.String)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					name := p.Args["name"].(string)
					email := p.Args["email"].(string)
					var id int
					var t time.Time
					err := db.QueryRow(`INSERT INTO users(name,email) VALUES($1,$2) RETURNING id,created_at`, name, email).Scan(&id, &t)
					if err != nil {
						return nil, err
					}
					return rowToUser(id, name, email, t), nil
				},
			},
			"update_user": &graphql.Field{
				Type: userType,
				Args: graphql.FieldConfigArgument{
					"id":    &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
					"name":  &graphql.ArgumentConfig{Type: graphql.String},
					"email": &graphql.ArgumentConfig{Type: graphql.String},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					id := p.Args["id"].(int)
					name, _ := p.Args["name"].(string)
					email, _ := p.Args["email"].(string)
					var uid int
					var n, e string
					var t time.Time
					err := db.QueryRow(`UPDATE users SET name=COALESCE(NULLIF($1,''),name),email=COALESCE(NULLIF($2,''),email) WHERE id=$3 RETURNING id,name,email,created_at`,
						name, email, id).Scan(&uid, &n, &e, &t)
					if err != nil {
						return nil, err
					}
					return rowToUser(uid, n, e, t), nil
				},
			},
			"delete_user": &graphql.Field{
				Type: graphql.Boolean,
				Args: graphql.FieldConfigArgument{
					"id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					db.Exec(`DELETE FROM users WHERE id=$1`, p.Args["id"].(int))
					return true, nil
				},
			},
			// Song mutations
			"create_song": &graphql.Field{
				Type: songType,
				Args: graphql.FieldConfigArgument{
					"title":            &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.String)},
					"artist":           &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.String)},
					"album":            &graphql.ArgumentConfig{Type: graphql.String},
					"year":             &graphql.ArgumentConfig{Type: graphql.Int},
					"genre":            &graphql.ArgumentConfig{Type: graphql.String},
					"duration_seconds": &graphql.ArgumentConfig{Type: graphql.Int},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					title := p.Args["title"].(string)
					artist := p.Args["artist"].(string)
					album, _ := p.Args["album"].(string)
					year, _ := p.Args["year"].(int)
					genre, _ := p.Args["genre"].(string)
					dur, _ := p.Args["duration_seconds"].(int)
					var id, yr, d int
					var ti, ar, al, g string
					var t time.Time
					err := db.QueryRow(`INSERT INTO songs(title,artist,album,year,genre,duration_seconds) VALUES($1,$2,$3,$4,$5,$6) RETURNING `+songCols,
						title, artist, album, year, genre, dur).Scan(&id, &ti, &ar, &al, &yr, &g, &d, &t)
					if err != nil {
						return nil, err
					}
					return rowToSong(id, ti, ar, al, yr, g, d, t), nil
				},
			},
			"delete_song": &graphql.Field{
				Type: graphql.Boolean,
				Args: graphql.FieldConfigArgument{
					"id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					db.Exec(`DELETE FROM songs WHERE id=$1`, p.Args["id"].(int))
					return true, nil
				},
			},
			// Playlist mutations
			"create_playlist": &graphql.Field{
				Type: playlistType,
				Args: graphql.FieldConfigArgument{
					"user_id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
					"name":    &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.String)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					uid := p.Args["user_id"].(int)
					name := p.Args["name"].(string)
					var id int
					var t time.Time
					err := db.QueryRow(`INSERT INTO playlists(user_id,name) VALUES($1,$2) RETURNING id,created_at`, uid, name).Scan(&id, &t)
					if err != nil {
						return nil, err
					}
					return rowToPlaylist(id, uid, name, t), nil
				},
			},
			"delete_playlist": &graphql.Field{
				Type: graphql.Boolean,
				Args: graphql.FieldConfigArgument{
					"id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					db.Exec(`DELETE FROM playlists WHERE id=$1`, p.Args["id"].(int))
					return true, nil
				},
			},
			"add_song_to_playlist": &graphql.Field{
				Type: graphql.Boolean,
				Args: graphql.FieldConfigArgument{
					"playlist_id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
					"song_id":     &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					db.Exec(`INSERT INTO playlist_songs(playlist_id,song_id) VALUES($1,$2) ON CONFLICT DO NOTHING`,
						p.Args["playlist_id"].(int), p.Args["song_id"].(int))
					return true, nil
				},
			},
			"remove_song_from_playlist": &graphql.Field{
				Type: graphql.Boolean,
				Args: graphql.FieldConfigArgument{
					"playlist_id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
					"song_id":     &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					db.Exec(`DELETE FROM playlist_songs WHERE playlist_id=$1 AND song_id=$2`,
						p.Args["playlist_id"].(int), p.Args["song_id"].(int))
					return true, nil
				},
			},
		},
	})

	var err error
	schema, err = graphql.NewSchema(graphql.SchemaConfig{
		Query:    rootQuery,
		Mutation: rootMutation,
	})
	if err != nil {
		log.Fatalf("Failed to build schema: %v", err)
	}
}

// ── HTTP handler ──────────────────────────────────────────────

func graphqlHandler(w http.ResponseWriter, r *http.Request) {
	var params struct {
		Query     string                 `json:"query"`
		Variables map[string]interface{} `json:"variables"`
	}
	json.NewDecoder(r.Body).Decode(&params)

	result := graphql.Do(graphql.Params{
		Schema:         schema,
		RequestString:  params.Query,
		VariableValues: params.Variables,
	})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

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

	buildSchema()

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})
	http.HandleFunc("/graphql", graphqlHandler)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8002"
	}
	log.Printf("Go GraphQL listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
