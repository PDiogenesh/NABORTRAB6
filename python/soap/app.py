import os, time
from spyne import Application, rpc, ServiceBase, Integer, Unicode, Iterable
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from sqlalchemy import create_engine, text
from wsgiref.simple_server import make_server

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://music:music123@localhost:5432/musicdb")

def get_engine():
    for i in range(30):
        try:
            eng = create_engine(DATABASE_URL, pool_pre_ping=True)
            with eng.connect() as c: c.execute(text("SELECT 1"))
            print("DB connected!"); return eng
        except Exception as e:
            print(f"Waiting for DB ({i+1}/30): {e}"); time.sleep(2)
    raise RuntimeError("DB unavailable")

engine = get_engine()

SONG_SEL = ("SELECT id, title, artist, COALESCE(album,'') as album, COALESCE(year,0) as year, "
            "COALESCE(genre,'') as genre, COALESCE(duration_seconds,0) as dur, created_at")

TNS = "http://music.example.com/soap"

# ── Spyne complex types ───────────────────────────────────────
from spyne import ComplexModel

class UserModel(ComplexModel):
    class Attributes(ComplexModel.Attributes):
        sqla_metadata = None
    id = Integer
    name = Unicode
    email = Unicode
    created_at = Unicode

class SongModel(ComplexModel):
    id = Integer; title = Unicode; artist = Unicode; album = Unicode
    year = Integer; genre = Unicode; duration_seconds = Integer; created_at = Unicode

class PlaylistModel(ComplexModel):
    id = Integer; user_id = Integer; name = Unicode; created_at = Unicode

# ── Helper ────────────────────────────────────────────────────

def row_to_user(r):
    u = UserModel(); u.id = r[0]; u.name = r[1]; u.email = r[2]; u.created_at = str(r[3])
    return u

def row_to_song(r):
    s = SongModel(); s.id = r[0]; s.title = r[1]; s.artist = r[2]; s.album = r[3]
    s.year = r[4]; s.genre = r[5]; s.duration_seconds = r[6]; s.created_at = str(r[7])
    return s

def row_to_pl(r):
    p = PlaylistModel(); p.id = r[0]; p.user_id = r[1]; p.name = r[2]; p.created_at = str(r[3])
    return p

# ── Service ───────────────────────────────────────────────────

class MusicService(ServiceBase):

    @rpc(_returns=Iterable(UserModel))
    def ListUsers(ctx):
        with engine.connect() as c:
            for r in c.execute(text("SELECT id,name,email,created_at FROM users ORDER BY id")):
                yield row_to_user(r)

    @rpc(Integer, _returns=UserModel)
    def GetUser(ctx, id):
        with engine.connect() as c:
            r = c.execute(text("SELECT id,name,email,created_at FROM users WHERE id=:id"), {"id": id}).fetchone()
        return row_to_user(r) if r else None

    @rpc(Unicode, Unicode, _returns=UserModel)
    def CreateUser(ctx, name, email):
        with engine.connect() as c:
            r = c.execute(text("INSERT INTO users(name,email) VALUES(:n,:e) RETURNING id,name,email,created_at"),
                          {"n": name, "e": email}).fetchone()
            c.commit()
        return row_to_user(r)

    @rpc(Integer, Unicode, Unicode, _returns=UserModel)
    def UpdateUser(ctx, id, name, email):
        with engine.connect() as c:
            r = c.execute(text("UPDATE users SET name=:n,email=:e WHERE id=:id RETURNING id,name,email,created_at"),
                          {"n": name, "e": email, "id": id}).fetchone()
            c.commit()
        return row_to_user(r) if r else None

    @rpc(Integer, _returns=Unicode)
    def DeleteUser(ctx, id):
        with engine.connect() as c:
            c.execute(text("DELETE FROM users WHERE id=:id"), {"id": id}); c.commit()
        return "ok"

    @rpc(_returns=Iterable(SongModel))
    def ListSongs(ctx):
        with engine.connect() as c:
            for r in c.execute(text(f"{SONG_SEL} FROM songs ORDER BY id")):
                yield row_to_song(r)

    @rpc(Integer, _returns=SongModel)
    def GetSong(ctx, id):
        with engine.connect() as c:
            r = c.execute(text(f"{SONG_SEL} FROM songs WHERE id=:id"), {"id": id}).fetchone()
        return row_to_song(r) if r else None

    @rpc(Unicode, Unicode, Unicode, Integer, Unicode, Integer, _returns=SongModel)
    def CreateSong(ctx, title, artist, album, year, genre, duration_seconds):
        with engine.connect() as c:
            r = c.execute(text(
                f"INSERT INTO songs(title,artist,album,year,genre,duration_seconds) "
                f"VALUES(:t,:a,:al,:y,:g,:d) RETURNING {SONG_SEL.split('SELECT ')[1]}"),
                {"t": title, "a": artist, "al": album, "y": year, "g": genre, "d": duration_seconds}).fetchone()
            c.commit()
        return row_to_song(r)

    @rpc(Integer, _returns=Unicode)
    def DeleteSong(ctx, id):
        with engine.connect() as c:
            c.execute(text("DELETE FROM songs WHERE id=:id"), {"id": id}); c.commit()
        return "ok"

    @rpc(Integer, Unicode, Unicode, Unicode, Integer, Unicode, Integer, _returns=SongModel)
    def UpdateSong(ctx, id, title, artist, album, year, genre, duration_seconds):
        with engine.connect() as c:
            r = c.execute(text(
                "UPDATE songs SET "
                "title=COALESCE(NULLIF(:t,''),title),"
                "artist=COALESCE(NULLIF(:a,''),artist),"
                "album=COALESCE(NULLIF(:al,''),album),"
                "year=CASE WHEN :y > 0 THEN :y ELSE year END,"
                "genre=COALESCE(NULLIF(:g,''),genre),"
                "duration_seconds=CASE WHEN :d > 0 THEN :d ELSE duration_seconds END "
                f"WHERE id=:id RETURNING {SONG_SEL.split('SELECT ')[1]}"
            ), {"t": title, "a": artist, "al": album, "y": year, "g": genre, "d": duration_seconds, "id": id}).fetchone()
            c.commit()
        return row_to_song(r) if r else None

    @rpc(_returns=Iterable(PlaylistModel))
    def ListPlaylists(ctx):
        with engine.connect() as c:
            for r in c.execute(text("SELECT id,user_id,name,created_at FROM playlists ORDER BY id")):
                yield row_to_pl(r)

    @rpc(Integer, _returns=PlaylistModel)
    def GetPlaylist(ctx, id):
        with engine.connect() as c:
            r = c.execute(text("SELECT id,user_id,name,created_at FROM playlists WHERE id=:id"), {"id": id}).fetchone()
        return row_to_pl(r) if r else None

    @rpc(Integer, _returns=Iterable(PlaylistModel))
    def ListPlaylistsByUser(ctx, user_id):
        with engine.connect() as c:
            for r in c.execute(text("SELECT id,user_id,name,created_at FROM playlists WHERE user_id=:uid ORDER BY id"), {"uid": user_id}):
                yield row_to_pl(r)

    @rpc(Integer, Unicode, _returns=PlaylistModel)
    def CreatePlaylist(ctx, user_id, name):
        with engine.connect() as c:
            r = c.execute(text("INSERT INTO playlists(user_id,name) VALUES(:uid,:n) RETURNING id,user_id,name,created_at"),
                          {"uid": user_id, "n": name}).fetchone()
            c.commit()
        return row_to_pl(r)

    @rpc(Integer, _returns=Unicode)
    def DeletePlaylist(ctx, id):
        with engine.connect() as c:
            c.execute(text("DELETE FROM playlists WHERE id=:id"), {"id": id}); c.commit()
        return "ok"

    @rpc(Integer, Unicode, _returns=PlaylistModel)
    def UpdatePlaylist(ctx, id, name):
        with engine.connect() as c:
            r = c.execute(text("UPDATE playlists SET name=:n WHERE id=:id RETURNING id,user_id,name,created_at"),
                          {"n": name, "id": id}).fetchone()
            c.commit()
        return row_to_pl(r) if r else None

    @rpc(Integer, _returns=Iterable(SongModel))
    def GetPlaylistSongs(ctx, playlist_id):
        with engine.connect() as c:
            for r in c.execute(text(
                "SELECT s.id,s.title,s.artist,COALESCE(s.album,''),COALESCE(s.year,0),"
                "COALESCE(s.genre,''),COALESCE(s.duration_seconds,0),s.created_at "
                "FROM songs s JOIN playlist_songs ps ON s.id=ps.song_id "
                "WHERE ps.playlist_id=:pid ORDER BY s.id"), {"pid": playlist_id}):
                yield row_to_song(r)

    @rpc(Integer, Integer, _returns=Unicode)
    def AddSongToPlaylist(ctx, playlist_id, song_id):
        with engine.connect() as c:
            c.execute(text("INSERT INTO playlist_songs(playlist_id,song_id) VALUES(:pid,:sid) ON CONFLICT DO NOTHING"),
                      {"pid": playlist_id, "sid": song_id}); c.commit()
        return "ok"

    @rpc(Integer, Integer, _returns=Unicode)
    def RemoveSongFromPlaylist(ctx, playlist_id, song_id):
        with engine.connect() as c:
            c.execute(text("DELETE FROM playlist_songs WHERE playlist_id=:pid AND song_id=:sid"),
                      {"pid": playlist_id, "sid": song_id}); c.commit()
        return "ok"


# ── WSGI app ──────────────────────────────────────────────────

application = Application(
    [MusicService],
    tns=TNS,
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11(),
)

wsgi_app = WsgiApplication(application)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8014"))
    print(f"Python SOAP listening on :{port}")
    server = make_server("0.0.0.0", port, wsgi_app)
    server.serve_forever()
