import http.server
import json
import ssl
import subprocess
import re
import os
from urllib.parse import urlparse


def generate_default_json(json_config_path):
    config = {
        "Foswiki": {
            "Password": "modell-aachen",
            "UseUnifiedAuth": True,
            "CustomConfig": {
                "{Register}{HidePasswd}": 0,
                "{UnifiedAuth}{ShowResetPassword}": 1,
                "{WebMasterName}": "Q.wiki test system",
                "{UnifiedAuth}{Providers}": {},
            },
        }
    }
    with open(json_config_path, "w") as file:
        json.dump(config, file, indent=2)


class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        url_path = urlparse(self.path).path
        pattern = r"^/listurl/\d+/configuration.*"

        if re.match(pattern, url_path):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            with open("/tmp/config.json", "rb") as file:
                self.wfile.write(file.read())
        else:
            super().do_GET()


def generate_certificate(pem_path, key_path):
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-keyout",
            key_path,
            "-out",
            pem_path,
            "-days",
            "365",
            "-nodes",
            "-subj",
            "/C=US/ST=State/L=City/O=Organization/CN=rms.modac.eu",
            "-addext",
            "subjectAltName=DNS:rms.modac.eu,IP:127.0.0.1",
        ],
        check=True,
    )


def trust_certificate(pem_path, crt_path):
    subprocess.run(["sudo", "cp", pem_path, crt_path], check=True)
    subprocess.run(["sudo", "update-ca-certificates"], check=True)


pem_path = "/usr/local/share/ca-certificates/local_rms.pem"
crt_path = "/usr/local/share/ca-certificates/local_rms.crt"
key_path = "/tmp/server_key.pem"
json_config_path = "/tmp/config.json"

if not os.path.exists(crt_path):
    generate_certificate(pem_path, key_path)
    trust_certificate(pem_path, crt_path)

if not os.path.exists(json_config_path):
    generate_default_json(json_config_path)

port = 443
server_address = ("localhost", port)
httpd = http.server.HTTPServer(server_address, CustomHTTPRequestHandler)

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain(certfile=pem_path, keyfile=key_path)

httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)

print(f"Serving HTTPS on port {port}...")
httpd.serve_forever()
