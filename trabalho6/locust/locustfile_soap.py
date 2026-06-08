"""
Locust load test for SOAP services.
Usage:
  locust -f locustfile_soap.py --host http://go-soap:8004 --headless -u 50 -r 5 --run-time 60s
"""
import random
from locust import HttpUser, task, between

def soap_body(operation, inner_xml):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://music.example.com/soap">'
        '<soap:Body>'
        f'<tns:{operation}>{inner_xml}</tns:{operation}>'
        '</soap:Body>'
        '</soap:Envelope>'
    )

HEADERS = {"Content-Type": "text/xml; charset=utf-8"}

class MusicSOAPUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def post(self, op, body="", name=None):
        self.client.post("/soap", data=soap_body(op, body),
                         headers=HEADERS, name=name or f"soap:{op}")

    @task(5)
    def get_song(self):
        sid = random.randint(1, 500)
        self.post("GetSong", f"<tns:id>{sid}</tns:id>", name="soap:GetSong")

    @task(3)
    def list_songs(self):
        self.post("ListSongs", name="soap:ListSongs")

    @task(3)
    def get_user(self):
        uid = random.randint(1, 300)
        self.post("GetUser", f"<tns:id>{uid}</tns:id>", name="soap:GetUser")

    @task(2)
    def list_users(self):
        self.post("ListUsers", name="soap:ListUsers")

    @task(3)
    def get_playlist(self):
        pid = random.randint(1, 100)
        self.post("GetPlaylist", f"<tns:id>{pid}</tns:id>", name="soap:GetPlaylist")

    @task(2)
    def list_playlists(self):
        self.post("ListPlaylists", name="soap:ListPlaylists")

    @task(2)
    def get_playlist_songs(self):
        pid = random.randint(1, 100)
        self.post("GetPlaylistSongs", f"<tns:playlist_id>{pid}</tns:playlist_id>", name="soap:GetPlaylistSongs")
