-- ============================================================
-- Music Streaming Service – Schema + Seed Data
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    email      VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS songs (
    id               SERIAL PRIMARY KEY,
    title            VARCHAR(255) NOT NULL,
    artist           VARCHAR(255) NOT NULL,
    album            VARCHAR(255),
    year             INTEGER,
    genre            VARCHAR(100),
    duration_seconds INTEGER,
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS playlists (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS playlist_songs (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    song_id     INTEGER NOT NULL REFERENCES songs(id)     ON DELETE CASCADE,
    PRIMARY KEY (playlist_id, song_id)
);

-- ── Seed ─────────────────────────────────────────────────────
DO $$
DECLARE
    i       INTEGER;
    j       INTEGER;
    genres  TEXT[] := ARRAY['Rock','Pop','Jazz','Blues','Classical',
                            'Hip-Hop','Electronic','Country','R&B','Metal'];
    artists TEXT[] := ARRAY['The Beatles','Led Zeppelin','Pink Floyd','Queen',
                            'Radiohead','Nirvana','Pearl Jam','Foo Fighters',
                            'Metallica','AC/DC','The Rolling Stones','David Bowie',
                            'Jimi Hendrix','Bob Dylan','Bruce Springsteen','U2',
                            'R.E.M.','Depeche Mode','New Order','Joy Division'];
    albums  TEXT[] := ARRAY['Abbey Road','Led Zeppelin IV','The Dark Side of the Moon',
                            'A Night at the Opera','OK Computer','Nevermind','Ten',
                            'The Colour and the Shape','Master of Puppets','Back in Black',
                            'Thriller','Born to Run','The Joshua Tree','Purple Rain',
                            'Rumours','Hotel California','Kind of Blue','What''s Going On'];
    words   TEXT[] := ARRAY['Midnight','Dancing','Forever','Lost','Dreams',
                            'Heaven','Thunder','Shadow','Silver','Golden'];
BEGIN
    -- 300 users
    FOR i IN 1..300 LOOP
        INSERT INTO users (name, email) VALUES (
            'User ' || i || ' ' || chr(65 + ((i-1) % 26)),
            'user' || i || '@music.example.com'
        ) ON CONFLICT (email) DO NOTHING;
    END LOOP;

    -- 500 songs
    FOR i IN 1..500 LOOP
        INSERT INTO songs (title, artist, album, year, genre, duration_seconds) VALUES (
            words[1 + ((i-1) % array_length(words,1))] || ' ' || chr(65+((i-1)%26)) || ' #' || i,
            artists[1 + ((i-1) % array_length(artists,1))],
            albums [1 + ((i-1) % array_length(albums, 1))],
            1960   + ((i-1) % 65),
            genres [1 + ((i-1) % array_length(genres, 1))],
            120    + ((i-1) % 300)
        );
    END LOOP;

    -- 100 playlists (1 per first 100 users)
    FOR i IN 1..100 LOOP
        INSERT INTO playlists (user_id, name) VALUES (
            i,
            CASE (i % 4)
                WHEN 0 THEN 'Workout Mix #'   || i
                WHEN 1 THEN 'Chill Vibes #'   || i
                WHEN 2 THEN 'Party Hits #'    || i
                ELSE        'Study Music #'   || i
            END
        );
    END LOOP;

    -- ~7 songs per playlist
    FOR i IN 1..100 LOOP
        FOR j IN 0..6 LOOP
            INSERT INTO playlist_songs (playlist_id, song_id)
            VALUES (i, 1 + ((i * 7 + j) % 500))
            ON CONFLICT DO NOTHING;
        END LOOP;
    END LOOP;
END $$;
