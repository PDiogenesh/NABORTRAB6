"""
Locust load test for GraphQL services.
Usage:
  locust -f locustfile_graphql.py --host http://go-graphql:8002 --headless -u 50 -r 5 --run-time 60s
"""
import random, json
from locust import HttpUser, task, between

GRAPHQL_ENDPOINT = "/graphql"

def gql(client, query, name="/graphql"):
    client.post(GRAPHQL_ENDPOINT, json={"query": query}, name=name,
                headers={"Content-Type": "application/json"})

class MusicGraphQLUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(5)
    def get_song(self):
        sid = random.randint(1, 500)
        gql(self.client, f"""{{ song(id: {sid}) {{ id title artist album year genre duration_seconds }} }}""",
            name="gql:song(id)")

    @task(3)
    def list_songs(self):
        gql(self.client, "{ songs { id title artist } }", name="gql:songs")

    @task(3)
    def get_user(self):
        uid = random.randint(1, 300)
        gql(self.client, f"{{ user(id: {uid}) {{ id name email }} }}", name="gql:user(id)")

    @task(2)
    def list_users(self):
        gql(self.client, "{ users { id name email } }", name="gql:users")

    @task(3)
    def get_playlist(self):
        pid = random.randint(1, 100)
        gql(self.client, f"{{ playlist(id: {pid}) {{ id user_id name }} }}", name="gql:playlist(id)")

    @task(2)
    def list_playlists(self):
        gql(self.client, "{ playlists { id user_id name } }", name="gql:playlists")

    @task(2)
    def get_playlist_songs(self):
        pid = random.randint(1, 100)
        gql(self.client, f"{{ playlist_songs(playlist_id: {pid}) {{ id title artist }} }}", name="gql:playlist_songs")
