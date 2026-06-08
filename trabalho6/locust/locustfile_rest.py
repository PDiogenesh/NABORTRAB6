"""
Locust load test for REST services (Go and Python).
Usage example:
  locust -f locustfile_rest.py --host http://go-rest:8001 --headless -u 50 -r 5 --run-time 60s
"""
import random
from locust import HttpUser, task, between

class MusicRESTUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        # Cache IDs available from DB seed
        self._song_ids  = list(range(1, 501))
        self._user_ids  = list(range(1, 301))
        self._pl_ids    = list(range(1, 101))

    # ── GET-heavy tasks (weight = count) ─────────────────────

    @task(5)
    def get_song(self):
        sid = random.choice(self._song_ids)
        self.client.get(f"/songs/{sid}", name="/songs/[id]")

    @task(3)
    def list_songs(self):
        self.client.get("/songs")

    @task(3)
    def get_user(self):
        uid = random.choice(self._user_ids)
        self.client.get(f"/users/{uid}", name="/users/[id]")

    @task(2)
    def list_users(self):
        self.client.get("/users")

    @task(3)
    def get_playlist(self):
        pid = random.choice(self._pl_ids)
        self.client.get(f"/playlists/{pid}", name="/playlists/[id]")

    @task(2)
    def list_playlists(self):
        self.client.get("/playlists")

    @task(2)
    def get_playlist_songs(self):
        pid = random.choice(self._pl_ids)
        self.client.get(f"/playlists/{pid}/songs", name="/playlists/[id]/songs")
