"""
Locust load test for gRPC services via gRPC-Web HTTP/1.1 proxy.
Because Locust's HTTP client can't speak raw gRPC, this file targets
the REST gateway shim (port 8001 / 8011) and is kept for the gRPC
comparison by running the raw gRPC client externally.

For direct gRPC benchmarking, use ghz:
  ghz --insecure --proto music.proto --call music.MusicService.GetSong \
      -d '{"id":42}' -n 5000 -c 50 go-grpc:8003

This file is a REST fallback that still exercises the same read patterns
so you can compare throughput numbers in Locust's unified dashboard.
"""
import random
from locust import HttpUser, task, between

class MusicGRPCFallbackUser(HttpUser):
    """
    Points at the Go-REST service as a stand-in baseline while
    the real gRPC numbers come from ghz / grpc-bench.
    Override --host when running.
    """
    wait_time = between(0.1, 0.5)

    @task(5)
    def get_song(self):
        sid = random.randint(1, 500)
        self.client.get(f"/songs/{sid}", name="/songs/[id]")

    @task(3)
    def list_songs(self):
        self.client.get("/songs")

    @task(3)
    def get_user(self):
        uid = random.randint(1, 300)
        self.client.get(f"/users/{uid}", name="/users/[id]")
