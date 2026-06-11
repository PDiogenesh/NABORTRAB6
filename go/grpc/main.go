package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net"
	"os"
	"time"

	_ "github.com/lib/pq"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	pb "grpc-server/musicpb"
)

// ── Server ────────────────────────────────────────────────────

type server struct {
	pb.UnimplementedMusicServiceServer
	db *sql.DB
}

const songCols = `id, title, artist, COALESCE(album,''), COALESCE(year,0), COALESCE(genre,''), COALESCE(duration_seconds,0), created_at`

func (s *server) rowToUser(id int32, name, email string, t time.Time) *pb.User {
	return &pb.User{Id: id, Name: name, Email: email, CreatedAt: t.Format(time.RFC3339)}
}

func (s *server) rowToSong(id int32, title, artist, album string, year int32, genre string, dur int32, t time.Time) *pb.Song {
	return &pb.Song{Id: id, Title: title, Artist: artist, Album: album, Year: year, Genre: genre, DurationSeconds: dur, CreatedAt: t.Format(time.RFC3339)}
}

func (s *server) rowToPlaylist(id, uid int32, name string, t time.Time) *pb.Playlist {
	return &pb.Playlist{Id: id, UserId: uid, Name: name, CreatedAt: t.Format(time.RFC3339)}
}

// ── Users ─────────────────────────────────────────────────────

func (s *server) ListUsers(_ context.Context, _ *pb.Empty) (*pb.UserList, error) {
	rows, err := s.db.Query(`SELECT id,name,email,created_at FROM users ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var users []*pb.User
	for rows.Next() {
		var id int32
		var name, email string
		var t time.Time
		rows.Scan(&id, &name, &email, &t)
		users = append(users, s.rowToUser(id, name, email, t))
	}
	return &pb.UserList{Users: users}, nil
}

func (s *server) GetUser(_ context.Context, req *pb.IdRequest) (*pb.User, error) {
	var id int32
	var name, email string
	var t time.Time
	err := s.db.QueryRow(`SELECT id,name,email,created_at FROM users WHERE id=$1`, req.Id).
		Scan(&id, &name, &email, &t)
	if err == sql.ErrNoRows {
		return nil, status.Error(codes.NotFound, "user not found")
	}
	return s.rowToUser(id, name, email, t), err
}

func (s *server) CreateUser(_ context.Context, req *pb.CreateUserReq) (*pb.User, error) {
	var id int32
	var t time.Time
	err := s.db.QueryRow(`INSERT INTO users(name,email) VALUES($1,$2) RETURNING id,created_at`, req.Name, req.Email).Scan(&id, &t)
	if err != nil {
		return nil, err
	}
	return s.rowToUser(id, req.Name, req.Email, t), nil
}

func (s *server) UpdateUser(_ context.Context, req *pb.UpdateUserReq) (*pb.User, error) {
	var id int32
	var name, email string
	var t time.Time
	err := s.db.QueryRow(`UPDATE users SET name=$1,email=$2 WHERE id=$3 RETURNING id,name,email,created_at`,
		req.Name, req.Email, req.Id).Scan(&id, &name, &email, &t)
	return s.rowToUser(id, name, email, t), err
}

func (s *server) DeleteUser(_ context.Context, req *pb.IdRequest) (*pb.Empty, error) {
	s.db.Exec(`DELETE FROM users WHERE id=$1`, req.Id)
	return &pb.Empty{}, nil
}

// ── Songs ─────────────────────────────────────────────────────

func (s *server) ListSongs(_ context.Context, _ *pb.Empty) (*pb.SongList, error) {
	rows, err := s.db.Query(`SELECT ` + songCols + ` FROM songs ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var songs []*pb.Song
	for rows.Next() {
		var id, year, dur int32
		var title, artist, album, genre string
		var t time.Time
		rows.Scan(&id, &title, &artist, &album, &year, &genre, &dur, &t)
		songs = append(songs, s.rowToSong(id, title, artist, album, year, genre, dur, t))
	}
	return &pb.SongList{Songs: songs}, nil
}

func (s *server) GetSong(_ context.Context, req *pb.IdRequest) (*pb.Song, error) {
	var id, year, dur int32
	var title, artist, album, genre string
	var t time.Time
	err := s.db.QueryRow(`SELECT `+songCols+` FROM songs WHERE id=$1`, req.Id).
		Scan(&id, &title, &artist, &album, &year, &genre, &dur, &t)
	if err == sql.ErrNoRows {
		return nil, status.Error(codes.NotFound, "song not found")
	}
	return s.rowToSong(id, title, artist, album, year, genre, dur, t), err
}

func (s *server) CreateSong(_ context.Context, req *pb.CreateSongReq) (*pb.Song, error) {
	var id, year, dur int32
	var title, artist, album, genre string
	var t time.Time
	err := s.db.QueryRow(`INSERT INTO songs(title,artist,album,year,genre,duration_seconds) VALUES($1,$2,$3,$4,$5,$6) RETURNING `+songCols,
		req.Title, req.Artist, req.Album, req.Year, req.Genre, req.DurationSeconds).
		Scan(&id, &title, &artist, &album, &year, &genre, &dur, &t)
	return s.rowToSong(id, title, artist, album, year, genre, dur, t), err
}

func (s *server) UpdateSong(_ context.Context, req *pb.UpdateSongReq) (*pb.Song, error) {
	var id, year, dur int32
	var title, artist, album, genre string
	var t time.Time
	err := s.db.QueryRow(`UPDATE songs SET title=$1,artist=$2,album=$3,year=$4,genre=$5,duration_seconds=$6 WHERE id=$7 RETURNING `+songCols,
		req.Title, req.Artist, req.Album, req.Year, req.Genre, req.DurationSeconds, req.Id).
		Scan(&id, &title, &artist, &album, &year, &genre, &dur, &t)
	return s.rowToSong(id, title, artist, album, year, genre, dur, t), err
}

func (s *server) DeleteSong(_ context.Context, req *pb.IdRequest) (*pb.Empty, error) {
	s.db.Exec(`DELETE FROM songs WHERE id=$1`, req.Id)
	return &pb.Empty{}, nil
}

// ── Playlists ─────────────────────────────────────────────────

func (s *server) ListPlaylists(_ context.Context, _ *pb.Empty) (*pb.PlaylistList, error) {
	rows, err := s.db.Query(`SELECT id,user_id,name,created_at FROM playlists ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var playlists []*pb.Playlist
	for rows.Next() {
		var id, uid int32
		var name string
		var t time.Time
		rows.Scan(&id, &uid, &name, &t)
		playlists = append(playlists, s.rowToPlaylist(id, uid, name, t))
	}
	return &pb.PlaylistList{Playlists: playlists}, nil
}

func (s *server) GetPlaylist(_ context.Context, req *pb.IdRequest) (*pb.Playlist, error) {
	var id, uid int32
	var name string
	var t time.Time
	err := s.db.QueryRow(`SELECT id,user_id,name,created_at FROM playlists WHERE id=$1`, req.Id).
		Scan(&id, &uid, &name, &t)
	if err == sql.ErrNoRows {
		return nil, status.Error(codes.NotFound, "playlist not found")
	}
	return s.rowToPlaylist(id, uid, name, t), err
}

func (s *server) ListPlaylistsByUser(_ context.Context, req *pb.IdRequest) (*pb.PlaylistList, error) {
	rows, err := s.db.Query(`SELECT id,user_id,name,created_at FROM playlists WHERE user_id=$1 ORDER BY id`, req.Id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var playlists []*pb.Playlist
	for rows.Next() {
		var id, uid int32
		var name string
		var t time.Time
		rows.Scan(&id, &uid, &name, &t)
		playlists = append(playlists, s.rowToPlaylist(id, uid, name, t))
	}
	return &pb.PlaylistList{Playlists: playlists}, nil
}

func (s *server) CreatePlaylist(_ context.Context, req *pb.CreatePlaylistReq) (*pb.Playlist, error) {
	var id int32
	var t time.Time
	err := s.db.QueryRow(`INSERT INTO playlists(user_id,name) VALUES($1,$2) RETURNING id,created_at`,
		req.UserId, req.Name).Scan(&id, &t)
	return s.rowToPlaylist(id, req.UserId, req.Name, t), err
}

func (s *server) UpdatePlaylist(_ context.Context, req *pb.UpdatePlaylistReq) (*pb.Playlist, error) {
	var id, uid int32
	var name string
	var t time.Time
	err := s.db.QueryRow(`UPDATE playlists SET name=$1 WHERE id=$2 RETURNING id,user_id,name,created_at`,
		req.Name, req.Id).Scan(&id, &uid, &name, &t)
	return s.rowToPlaylist(id, uid, name, t), err
}

func (s *server) DeletePlaylist(_ context.Context, req *pb.IdRequest) (*pb.Empty, error) {
	s.db.Exec(`DELETE FROM playlists WHERE id=$1`, req.Id)
	return &pb.Empty{}, nil
}

func (s *server) GetPlaylistSongs(_ context.Context, req *pb.IdRequest) (*pb.SongList, error) {
	rows, err := s.db.Query(`SELECT s.`+songCols+` FROM songs s JOIN playlist_songs ps ON s.id=ps.song_id WHERE ps.playlist_id=$1 ORDER BY s.id`, req.Id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var songs []*pb.Song
	for rows.Next() {
		var id, year, dur int32
		var title, artist, album, genre string
		var t time.Time
		rows.Scan(&id, &title, &artist, &album, &year, &genre, &dur, &t)
		songs = append(songs, s.rowToSong(id, title, artist, album, year, genre, dur, t))
	}
	return &pb.SongList{Songs: songs}, nil
}

func (s *server) AddSongToPlaylist(_ context.Context, req *pb.PlaylistSongReq) (*pb.Empty, error) {
	s.db.Exec(`INSERT INTO playlist_songs(playlist_id,song_id) VALUES($1,$2) ON CONFLICT DO NOTHING`, req.PlaylistId, req.SongId)
	return &pb.Empty{}, nil
}

func (s *server) RemoveSongFromPlaylist(_ context.Context, req *pb.PlaylistSongReq) (*pb.Empty, error) {
	s.db.Exec(`DELETE FROM playlist_songs WHERE playlist_id=$1 AND song_id=$2`, req.PlaylistId, req.SongId)
	return &pb.Empty{}, nil
}

// ── Main ──────────────────────────────────────────────────────

func main() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "postgres://music:music123@localhost:5432/musicdb?sslmode=disable"
	}

	var (
		dbConn *sql.DB
		err    error
	)
	for i := 0; i < 30; i++ {
		dbConn, err = sql.Open("postgres", dsn)
		if err == nil {
			if err = dbConn.Ping(); err == nil {
				break
			}
			dbConn.Close()
		}
		log.Printf("Waiting for DB (%d/30)…", i+1)
		time.Sleep(2 * time.Second)
	}
	if err != nil {
		log.Fatalf("DB unreachable: %v", err)
	}
	defer dbConn.Close()

	port := os.Getenv("PORT")
	if port == "" {
		port = "8003"
	}
	lis, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		log.Fatalf("listen: %v", err)
	}

	grpcServer := grpc.NewServer()
	pb.RegisterMusicServiceServer(grpcServer, &server{db: dbConn})

	log.Printf("Go gRPC listening on :%s", port)
	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("serve: %v", err)
	}
}
