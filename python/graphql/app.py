import os, time
from typing import List, Optional
import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig
from fastapi import FastAPI
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://music:music123@localhost:5432/musicdb")

def get_engine():
    for i in range(30):
        try:
            eng = create_engine(DATABASE_URL, pool_pre_ping=True)
            with eng.connect() as c: c.execute(text("SELECT 1"))
            print("DB connected!")
            return eng
        except Exception as e:
            print(f"Waiting for DB ({i+1}/30): {e}")
            time.sleep(2)
    raise RuntimeError("DB unavailable")

engine = get_engine()

SONG_SEL = ("SELECT id, title, artist, COALESCE(album,''), COALESCE(year,0), "
            "COALESCE(genre,''), COALESCE(duration_seconds,0), created_at")

# ── Types ─────────────────────────────────────────────────────

@strawberry.type
class User:
    id: int; name: str; email: str; created_at: str

@strawberry.type
class Song:
    id: int; title: str; artist: str; album: str
    year: int; genre: str; duration_seconds: int; created_at: str

@strawberry.type
class Playlist:
    id: int; user_id: int; name: str; created_at: str

# ── Inputs ────────────────────────────────────────────────────

@strawberry.input
class UserInput:
    name: str; email: str

@strawberry.input
class SongInput:
    title: str; artist: str
    album: str = ""; year: int = 0; genre: str = ""; duration_seconds: int = 0

@strawberry.input
class SongUpdateInput:
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    duration_seconds: Optional[int] = None

@strawberry.input
class PlaylistInput:
    user_id: int; name: str

# ── Row helpers ───────────────────────────────────────────────

def mk_user(r): return User(id=r[0], name=r[1], email=r[2], created_at=str(r[3]))
def mk_song(r): return Song(id=r[0], title=r[1], artist=r[2], album=r[3] or "",
                            year=r[4] or 0, genre=r[5] or "", duration_seconds=r[6] or 0,
                            created_at=str(r[7]))
def mk_pl(r):   return Playlist(id=r[0], user_id=r[1], name=r[2], created_at=str(r[3]))

# ── Query ─────────────────────────────────────────────────────

@strawberry.type
class Query:
    @strawberry.field
    def users(self) -> List[User]:
        with engine.connect() as c:
            return [mk_user(r) for r in c.execute(text("SELECT id,name,email,created_at FROM users ORDER BY id"))]

    @strawberry.field
    def user(self, id: int) -> Optional[User]:
        with engine.connect() as c:
            r = c.execute(text("SELECT id,name,email,created_at FROM users WHERE id=:id"), {"id": id}).fetchone()
        return mk_user(r) if r else None

    @strawberry.field
    def songs(self) -> List[Song]:
        with engine.connect() as c:
            return [mk_song(r) for r in c.execute(text(f"{SONG_SEL} FROM songs ORDER BY id"))]

    @strawberry.field
    def song(self, id: int) -> Optional[Song]:
        with engine.connect() as c:
            r = c.execute(text(f"{SONG_SEL} FROM songs WHERE id=:id"), {"id": id}).fetchone()
        return mk_song(r) if r else None

    @strawberry.field
    def playlists(self, user_id: Optional[int] = None) -> List[Playlist]:
        with engine.connect() as c:
            if user_id:
                rows = c.execute(text("SELECT id,user_id,name,created_at FROM playlists WHERE user_id=:uid ORDER BY id"), {"uid": user_id})
            else:
                rows = c.execute(text("SELECT id,user_id,name,created_at FROM playlists ORDER BY id"))
            return [mk_pl(r) for r in rows]

    @strawberry.field
    def playlist(self, id: int) -> Optional[Playlist]:
        with engine.connect() as c:
            r = c.execute(text("SELECT id,user_id,name,created_at FROM playlists WHERE id=:id"), {"id": id}).fetchone()
        return mk_pl(r) if r else None

    @strawberry.field
    def playlist_songs(self, playlist_id: int) -> List[Song]:
        with engine.connect() as c:
            rows = c.execute(text(
                "SELECT s.id,s.title,s.artist,COALESCE(s.album,''),COALESCE(s.year,0),"
                "COALESCE(s.genre,''),COALESCE(s.duration_seconds,0),s.created_at "
                "FROM songs s JOIN playlist_songs ps ON s.id=ps.song_id "
                "WHERE ps.playlist_id=:pid ORDER BY s.id"), {"pid": playlist_id})
            return [mk_song(r) for r in rows]

# ── Mutation ──────────────────────────────────────────────────

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, input: UserInput) -> User:
        with engine.connect() as c:
            r = c.execute(text("INSERT INTO users(name,email) VALUES(:n,:e) RETURNING id,name,email,created_at"),
                          {"n": input.name, "e": input.email}).fetchone()
            c.commit()
        return mk_user(r)

    @strawberry.mutation
    def update_user(self, id: int, input: UserInput) -> Optional[User]:
        with engine.connect() as c:
            r = c.execute(text("UPDATE users SET name=:n,email=:e WHERE id=:id RETURNING id,name,email,created_at"),
                          {"n": input.name, "e": input.email, "id": id}).fetchone()
            c.commit()
        return mk_user(r) if r else None

    @strawberry.mutation
    def delete_user(self, id: int) -> bool:
        with engine.connect() as c:
            c.execute(text("DELETE FROM users WHERE id=:id"), {"id": id}); c.commit()
        return True

    @strawberry.mutation
    def create_song(self, input: SongInput) -> Song:
        with engine.connect() as c:
            r = c.execute(text(
                f"INSERT INTO songs(title,artist,album,year,genre,duration_seconds) "
                f"VALUES(:t,:a,:al,:y,:g,:d) RETURNING {SONG_SEL.split('SELECT ')[1]}"),
                {"t": input.title, "a": input.artist, "al": input.album,
                 "y": input.year, "g": input.genre, "d": input.duration_seconds}).fetchone()
            c.commit()
        return mk_song(r)

    @strawberry.mutation
    def delete_song(self, id: int) -> bool:
        with engine.connect() as c:
            c.execute(text("DELETE FROM songs WHERE id=:id"), {"id": id}); c.commit()
        return True

    @strawberry.mutation
    def update_song(self, id: int, input: SongUpdateInput) -> Optional[Song]:
        with engine.connect() as c:
            r = c.execute(text(
                "UPDATE songs SET "
                "title=COALESCE(:t,title),"
                "artist=COALESCE(:a,artist),"
                "album=COALESCE(:al,album),"
                "year=COALESCE(:y,year),"
                "genre=COALESCE(:g,genre),"
                "duration_seconds=COALESCE(:d,duration_seconds) "
                f"WHERE id=:id RETURNING {SONG_SEL.split('SELECT ')[1]}"
            ), {"t": input.title, "a": input.artist, "al": input.album,
                "y": input.year, "g": input.genre, "d": input.duration_seconds, "id": id}).fetchone()
            c.commit()
        return mk_song(r) if r else None

    @strawberry.mutation
    def create_playlist(self, input: PlaylistInput) -> Playlist:
        with engine.connect() as c:
            r = c.execute(text("INSERT INTO playlists(user_id,name) VALUES(:uid,:n) RETURNING id,user_id,name,created_at"),
                          {"uid": input.user_id, "n": input.name}).fetchone()
            c.commit()
        return mk_pl(r)

    @strawberry.mutation
    def update_playlist(self, id: int, name: str) -> Optional[Playlist]:
        with engine.connect() as c:
            r = c.execute(text("UPDATE playlists SET name=:n WHERE id=:id RETURNING id,user_id,name,created_at"),
                          {"n": name, "id": id}).fetchone()
            c.commit()
        return mk_pl(r) if r else None

    @strawberry.mutation
    def delete_playlist(self, id: int) -> bool:
        with engine.connect() as c:
            c.execute(text("DELETE FROM playlists WHERE id=:id"), {"id": id}); c.commit()
        return True

    @strawberry.mutation
    def add_song_to_playlist(self, playlist_id: int, song_id: int) -> bool:
        with engine.connect() as c:
            c.execute(text("INSERT INTO playlist_songs(playlist_id,song_id) VALUES(:pid,:sid) ON CONFLICT DO NOTHING"),
                      {"pid": playlist_id, "sid": song_id}); c.commit()
        return True

    @strawberry.mutation
    def remove_song_from_playlist(self, playlist_id: int, song_id: int) -> bool:
        with engine.connect() as c:
            c.execute(text("DELETE FROM playlist_songs WHERE playlist_id=:pid AND song_id=:sid"),
                      {"pid": playlist_id, "sid": song_id}); c.commit()
        return True

# ── App ───────────────────────────────────────────────────────

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    config=StrawberryConfig(auto_camel_case=False)
)

graphql_router = GraphQLRouter(schema)
app = FastAPI(title="Music Service – Python GraphQL")
app.include_router(graphql_router, prefix="/graphql")

@app.get("/health")
def health(): return {"status": "ok"}
