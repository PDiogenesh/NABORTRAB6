import os, time
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://music:music123@localhost:5432/musicdb")

def get_engine():
    for i in range(30):
        try:
            eng = create_engine(DATABASE_URL, pool_pre_ping=True)
            with eng.connect() as c:
                c.execute(text("SELECT 1"))
            print("DB connected!")
            return eng
        except Exception as e:
            print(f"Waiting for DB ({i+1}/30): {e}")
            time.sleep(2)
    raise RuntimeError("DB unavailable")

engine = get_engine()
app = FastAPI(title="Music Service – Python REST")

# ── Pydantic models ───────────────────────────────────────────

class UserCreate(BaseModel):
    name: str; email: str

class UserUpdate(BaseModel):
    name: Optional[str] = None; email: Optional[str] = None

class SongCreate(BaseModel):
    title: str; artist: str
    album: Optional[str] = None; year: Optional[int] = None
    genre: Optional[str] = None; duration_seconds: Optional[int] = None

class SongUpdate(BaseModel):
    title: Optional[str] = None; artist: Optional[str] = None
    album: Optional[str] = None; year: Optional[int] = None
    genre: Optional[str] = None; duration_seconds: Optional[int] = None

class PlaylistCreate(BaseModel):
    user_id: int; name: str

class PlaylistUpdate(BaseModel):
    name: Optional[str] = None

class PlaylistSongAdd(BaseModel):
    song_id: int

# ── Row helpers ───────────────────────────────────────────────

def r_user(r):
    return {"id": r[0], "name": r[1], "email": r[2], "created_at": str(r[3])}

def r_song(r):
    return {"id": r[0], "title": r[1], "artist": r[2], "album": r[3] or "",
            "year": r[4] or 0, "genre": r[5] or "", "duration_seconds": r[6] or 0,
            "created_at": str(r[7])}

def r_pl(r):
    return {"id": r[0], "user_id": r[1], "name": r[2], "created_at": str(r[3])}

SONG_SEL = ("SELECT id, title, artist, COALESCE(album,''), COALESCE(year,0), "
            "COALESCE(genre,''), COALESCE(duration_seconds,0), created_at")

# ── Health ────────────────────────────────────────────────────

@app.get("/health")
def health(): return {"status": "ok"}

# ── Users ─────────────────────────────────────────────────────

@app.get("/users")
def list_users():
    with engine.connect() as c:
        return [r_user(r) for r in c.execute(text("SELECT id,name,email,created_at FROM users ORDER BY id"))]

@app.get("/users/{uid}")
def get_user(uid: int):
    with engine.connect() as c:
        r = c.execute(text("SELECT id,name,email,created_at FROM users WHERE id=:id"), {"id": uid}).fetchone()
    if not r: raise HTTPException(404, "User not found")
    return r_user(r)

@app.post("/users", status_code=201)
def create_user(u: UserCreate):
    with engine.connect() as c:
        r = c.execute(text("INSERT INTO users(name,email) VALUES(:n,:e) RETURNING id,name,email,created_at"),
                      {"n": u.name, "e": u.email}).fetchone()
        c.commit()
    return r_user(r)

@app.put("/users/{uid}")
def update_user(uid: int, u: UserUpdate):
    with engine.connect() as c:
        r = c.execute(text("UPDATE users SET name=COALESCE(:n,name), email=COALESCE(:e,email) WHERE id=:id RETURNING id,name,email,created_at"),
                      {"n": u.name, "e": u.email, "id": uid}).fetchone()
        c.commit()
    if not r: raise HTTPException(404, "User not found")
    return r_user(r)

@app.delete("/users/{uid}", status_code=204)
def delete_user(uid: int):
    with engine.connect() as c:
        c.execute(text("DELETE FROM users WHERE id=:id"), {"id": uid}); c.commit()

# ── Songs ─────────────────────────────────────────────────────

@app.get("/songs")
def list_songs():
    with engine.connect() as c:
        return [r_song(r) for r in c.execute(text(f"{SONG_SEL} FROM songs ORDER BY id"))]

@app.get("/songs/{sid}")
def get_song(sid: int):
    with engine.connect() as c:
        r = c.execute(text(f"{SONG_SEL} FROM songs WHERE id=:id"), {"id": sid}).fetchone()
    if not r: raise HTTPException(404, "Song not found")
    return r_song(r)

@app.post("/songs", status_code=201)
def create_song(s: SongCreate):
    with engine.connect() as c:
        r = c.execute(text(f"INSERT INTO songs(title,artist,album,year,genre,duration_seconds) "
                           f"VALUES(:t,:a,:al,:y,:g,:d) RETURNING {SONG_SEL.split('SELECT ')[1]}"),
                      {"t": s.title, "a": s.artist, "al": s.album, "y": s.year,
                       "g": s.genre, "d": s.duration_seconds}).fetchone()
        c.commit()
    return r_song(r)

@app.put("/songs/{sid}")
def update_song(sid: int, s: SongUpdate):
    with engine.connect() as c:
        r = c.execute(text(f"UPDATE songs SET title=COALESCE(:t,title),artist=COALESCE(:a,artist),"
                           f"album=COALESCE(:al,album),year=COALESCE(:y,year),"
                           f"genre=COALESCE(:g,genre),duration_seconds=COALESCE(:d,duration_seconds) "
                           f"WHERE id=:id RETURNING {SONG_SEL.split('SELECT ')[1]}"),
                      {"t": s.title, "a": s.artist, "al": s.album, "y": s.year,
                       "g": s.genre, "d": s.duration_seconds, "id": sid}).fetchone()
        c.commit()
    if not r: raise HTTPException(404, "Song not found")
    return r_song(r)

@app.delete("/songs/{sid}", status_code=204)
def delete_song(sid: int):
    with engine.connect() as c:
        c.execute(text("DELETE FROM songs WHERE id=:id"), {"id": sid}); c.commit()

# ── Playlists ─────────────────────────────────────────────────

@app.get("/playlists")
def list_playlists(user_id: Optional[int] = None):
    with engine.connect() as c:
        if user_id:
            rows = c.execute(text("SELECT id,user_id,name,created_at FROM playlists WHERE user_id=:uid ORDER BY id"), {"uid": user_id})
        else:
            rows = c.execute(text("SELECT id,user_id,name,created_at FROM playlists ORDER BY id"))
        return [r_pl(r) for r in rows]

@app.get("/playlists/{pid}")
def get_playlist(pid: int):
    with engine.connect() as c:
        r = c.execute(text("SELECT id,user_id,name,created_at FROM playlists WHERE id=:id"), {"id": pid}).fetchone()
    if not r: raise HTTPException(404, "Playlist not found")
    return r_pl(r)

@app.post("/playlists", status_code=201)
def create_playlist(pl: PlaylistCreate):
    with engine.connect() as c:
        r = c.execute(text("INSERT INTO playlists(user_id,name) VALUES(:uid,:n) RETURNING id,user_id,name,created_at"),
                      {"uid": pl.user_id, "n": pl.name}).fetchone()
        c.commit()
    return r_pl(r)

@app.put("/playlists/{pid}")
def update_playlist(pid: int, pl: PlaylistUpdate):
    with engine.connect() as c:
        r = c.execute(text("UPDATE playlists SET name=COALESCE(:n,name) WHERE id=:id RETURNING id,user_id,name,created_at"),
                      {"n": pl.name, "id": pid}).fetchone()
        c.commit()
    if not r: raise HTTPException(404, "Playlist not found")
    return r_pl(r)

@app.delete("/playlists/{pid}", status_code=204)
def delete_playlist(pid: int):
    with engine.connect() as c:
        c.execute(text("DELETE FROM playlists WHERE id=:id"), {"id": pid}); c.commit()

@app.get("/playlists/{pid}/songs")
def get_playlist_songs(pid: int):
    with engine.connect() as c:
        rows = c.execute(text(f"SELECT s.id,s.title,s.artist,COALESCE(s.album,''),COALESCE(s.year,0),"
                              f"COALESCE(s.genre,''),COALESCE(s.duration_seconds,0),s.created_at "
                              f"FROM songs s JOIN playlist_songs ps ON s.id=ps.song_id WHERE ps.playlist_id=:pid ORDER BY s.id"),
                         {"pid": pid})
        return [r_song(r) for r in rows]

@app.post("/playlists/{pid}/songs", status_code=201)
def add_song(pid: int, body: PlaylistSongAdd):
    with engine.connect() as c:
        c.execute(text("INSERT INTO playlist_songs(playlist_id,song_id) VALUES(:pid,:sid) ON CONFLICT DO NOTHING"),
                  {"pid": pid, "sid": body.song_id}); c.commit()

@app.delete("/playlists/{pid}/songs/{sid}", status_code=204)
def remove_song(pid: int, sid: int):
    with engine.connect() as c:
        c.execute(text("DELETE FROM playlist_songs WHERE playlist_id=:pid AND song_id=:sid"),
                  {"pid": pid, "sid": sid}); c.commit()
