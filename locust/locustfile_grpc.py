"""
Locust load test for gRPC services (Go and Python).
Usage:
  locust -f locustfile_grpc.py --host http://localhost:8003 --headless -u 50 -r 5 --run-time 60s
"""
import time
import random
import os
import sys
import grpc
import grpc.experimental.gevent

# Initialize gevent support for gRPC to prevent blocking the gevent event loop
grpc.experimental.gevent.init_gevent()

from locust import User, task, between

# Add the current directory to path to import generated proto code
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import music_pb2
import music_pb2_grpc

class MusicGRPCUser(User):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        # self.host is provided by locust (e.g. "http://localhost:8003" or "http://go-grpc:8003")
        # Strip protocol prefix to get raw hostname and port
        host = self.host.replace("http://", "").replace("https://", "")
        self.channel = grpc.insecure_channel(host)
        self.stub = music_pb2_grpc.MusicServiceStub(self.channel)

    def on_stop(self):
        self.channel.close()

    def _fire_request(self, name, start_time, response_length=0, exception=None):
        total_time = (time.perf_counter() - start_time) * 1000
        self.environment.events.request.fire(
            request_type="grpc",
            name=name,
            response_time=total_time,
            response_length=response_length,
            exception=exception,
        )

    @task(5)
    def get_song(self):
        sid = random.randint(1, 500)
        start_time = time.perf_counter()
        try:
            res = self.stub.GetSong(music_pb2.IdRequest(id=sid), timeout=5)
            self._fire_request("GetSong", start_time, response_length=res.ByteSize())
        except Exception as e:
            self._fire_request("GetSong", start_time, exception=e)

    @task(3)
    def list_songs(self):
        start_time = time.perf_counter()
        try:
            res = self.stub.ListSongs(music_pb2.Empty(), timeout=5)
            self._fire_request("ListSongs", start_time, response_length=res.ByteSize())
        except Exception as e:
            self._fire_request("ListSongs", start_time, exception=e)

    @task(3)
    def get_user(self):
        uid = random.randint(1, 300)
        start_time = time.perf_counter()
        try:
            res = self.stub.GetUser(music_pb2.IdRequest(id=uid), timeout=5)
            self._fire_request("GetUser", start_time, response_length=res.ByteSize())
        except Exception as e:
            self._fire_request("GetUser", start_time, exception=e)

    @task(2)
    def list_users(self):
        start_time = time.perf_counter()
        try:
            res = self.stub.ListUsers(music_pb2.Empty(), timeout=5)
            self._fire_request("ListUsers", start_time, response_length=res.ByteSize())
        except Exception as e:
            self._fire_request("ListUsers", start_time, exception=e)

    @task(3)
    def get_playlist(self):
        pid = random.randint(1, 100)
        start_time = time.perf_counter()
        try:
            res = self.stub.GetPlaylist(music_pb2.IdRequest(id=pid), timeout=5)
            self._fire_request("GetPlaylist", start_time, response_length=res.ByteSize())
        except Exception as e:
            self._fire_request("GetPlaylist", start_time, exception=e)

    @task(2)
    def list_playlists(self):
        start_time = time.perf_counter()
        try:
            res = self.stub.ListPlaylists(music_pb2.Empty(), timeout=5)
            self._fire_request("ListPlaylists", start_time, response_length=res.ByteSize())
        except Exception as e:
            self._fire_request("ListPlaylists", start_time, exception=e)

    @task(2)
    def get_playlist_songs(self):
        pid = random.randint(1, 100)
        start_time = time.perf_counter()
        try:
            res = self.stub.GetPlaylistSongs(music_pb2.IdRequest(id=pid), timeout=5)
            self._fire_request("GetPlaylistSongs", start_time, response_length=res.ByteSize())
        except Exception as e:
            self._fire_request("GetPlaylistSongs", start_time, exception=e)
