import http.server
import threading
import urllib.parse
import os
from dotenv import load_dotenv
import time
from utils.log_util import get_logger
logger = get_logger(__name__)

load_dotenv()
TWITCH_REDIRECT_URI = os.getenv("TWITCH_REDIRECT_URI")

# Parse the redirect URI and return (host, port, path).
def _parse_redirect_host_port_and_path(redirect_uri: str):
  # Defaults: host=localhost if missing; port=8080 if missing; path=/ if missing.
  if redirect_uri:
    (f"Existing redirect uri: {redirect_uri}")
  parsed = urllib.parse.urlparse(redirect_uri)
  host = parsed.hostname or "localhost"
  port = parsed.port or 8080
  path = parsed.path or "/"
  logger.info(f"Redirect uri: http://{host}:{port}{path}")
  return host, port, path


class _TwitchCallbackRequestHandler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
    parsed_url = urllib.parse.urlparse(self.path)
    path = parsed_url.path

    # Only handle the configured callback path
    if path != getattr(self.server, "callback_path", "/callback"):
      self.send_response(404)
      self.end_headers()
      self.wfile.write(b"Not found")
      return
    
    # Get fragment from parsed url
    query = urllib.parse.parse_qs(parsed_url.query or "")
    state = query.get("state", [None])[0]
    code = query.get("code", [None])[0]
    error = query.get("error", [None])[0]

    expected_state = getattr(self.server, "expected_state", None)

    # Validate state (CSRF protection)
    if expected_state and state != expected_state:
      self.server.auth_error = "invalid_state"
      self.send_response(400)
      self.end_headers()
      self.wfile.write(b"Invalid state parameter")
      return

    # Handle explicit error from Twitch
    if error:
      self.server.auth_error = error
      self.send_response(400)
      self.end_headers()
      self.wfile.write(b"Error during authentication")
      return

    # Throw error if no code is found
    if not code:
      self.server.auth_error = "missing_code"
      self.send_response(400)
      self.end_headers()
      self.wfile.write(b"Missing authorization code")
      return

    # Success: store the code on the server and respond once
    self.server.auth_code = code
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"Authorization successful. You can close this window.")

  def log_message(self, format, *args):
    # Silence default HTTP logging to avoid noisy console output
    pass

# Local http server for callback
class TwitchCallbackServer:

  def __init__(self, expected_state: str, timeout_seconds: int = 300):
    self.expected_state = expected_state
    self.timeout_seconds = timeout_seconds
    self._server = None
    self._thread = None

  def start(self):
    # Fetch callback uri info from env
    host, port, path = _parse_redirect_host_port_and_path(TWITCH_REDIRECT_URI)
    httpd = http.server.HTTPServer((host, port), _TwitchCallbackRequestHandler)
    httpd.expected_state = self.expected_state
    httpd.callback_path = path
    httpd.auth_code = None
    httpd.auth_error = None

    self._server = httpd

    # New thread for server
    self._thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    self._thread.start()
    logger.info(f"Starting Twitch callback server on {host}:{port}{path}")

  def wait_for_code(self):
    # Check for either the code or an error
    if not self._server:
        raise RuntimeError("Callback server not started")

    start = time.time()
    while time.time() - start < self.timeout_seconds:
        if self._server.auth_code is not None or self._server.auth_error is not None:
            return self._server.auth_code, self._server.auth_error
        time.sleep(0.2)

    # Timed out
    return None, "timeout"

  def stop(self):
    if self._server:
      self._server.shutdown()
      self._server.server_close()
      self._server = None
      print("Twitch callback server stopped")