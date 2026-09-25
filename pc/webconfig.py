"""A little local page for setting the launcher's six slots.

    python3 -m pc.webconfig        then open http://127.0.0.1:8730

Editing ~/.overwatch/apps.json by hand works and always will; this exists because
the file wants app names spelled exactly as `open -a` needs them, and getting
"Adobe Photoshop 2026" right from memory is the sort of thing that fails
silently as a tile that lights and launches nothing.

Standard library only (CLAUDE.md), so no framework and no build step - one
page, served inline.

BOUND TO LOOPBACK, deliberately. This endpoint writes a file that decides
which programs a tap on the desk can start. 127.0.0.1 means a machine on the
same network cannot reach it; binding 0.0.0.0 would turn the panel into a
remote execution surface for anyone on the café wifi.
"""
import html
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

if __package__ in (None, ""):
    # Run as `python3 pc/webconfig.py`, Python puts pc/ on the path and not
    # the project root, so `from pc import ...` cannot resolve. Put the root
    # back so the file works whether it is run as a script or as `-m`.
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pc import cli, widgets

HOST, PORT = "127.0.0.1", 8730

# The page on GitHub Pages is allowed to talk to this daemon. Nothing else
# off-machine is: the list is exact, not a pattern, because a wildcard here
# hands the launcher to whoever registers a lookalike host.
ALLOWED_ORIGINS = ("https://sleepyunicon.github.io",)

TOKEN_HEADER = "X-Overwatch-Token"


def _origin_ok(origin):
    """Is this origin allowed to be ANSWERED? Not the same as allowed to act.

    The published page, plus anything already served from this machine.
    Loopback is here because a page on 127.0.0.1 is being served by
    something that is already running locally -- reaching it needed code on
    the machine, which is a bigger win than anything this endpoint offers.

    It is not the security boundary either way. The token is: every one of
    these origins still has to present it, so widening this list widens who
    may ASK, never who may act.
    """
    if not origin:
        return False
    if origin in ALLOWED_ORIGINS:
        return True
    return (origin.startswith("http://127.0.0.1:")
            or origin.startswith("http://localhost:"))

# The real interface. This daemon serves an API and a one-click way into it;
# the page itself lives on Pages, where it can be fixed without reflashing
# anybody's install.
APP_URL = "https://sleepyunicon.github.io/Overwatch/"

# Set by serve_background(), which only the daemon calls. When this page is
# served from inside the daemon the question "is the daemon running?" has a
# certain answer, and it should not be guessed at from a pid file.
IN_DAEMON = False

START_WAIT_S = 12.0   # how long /api/daemon/start waits for it to come up

# Outlive the page that started it. This is usually a short-lived
# `python3 -m pc.webconfig`, and a daemon started as its child would die with
# the terminal it came from. setsid on POSIX; on Windows the same idea spelt
# DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, in the style of ota.NO_WINDOW.
DETACHED = ({"creationflags": 0x00000008 | 0x00000200}
            if sys.platform == "win32" else {"start_new_session": True})
APP_DIRS = ("/Applications", os.path.expanduser("~/Applications"),
            "/System/Applications")


def installed_apps():
    """Every .app on this Mac, by the name `open -a` wants.

    That is the BUNDLE name without .app - not the display name, not the path.
    Sorted and de-duplicated because /Applications and ~/Applications overlap
    on plenty of machines.
    """
    found = set()
    for d in APP_DIRS:
        if not os.path.isdir(d):
            continue
        for entry in os.listdir(d):
            if entry.endswith(".app"):
                found.add(entry[:-4])
            else:
                # Adobe and a few others nest the bundle one level down
                sub = os.path.join(d, entry)
                if os.path.isdir(sub):
                    try:
                        for e2 in os.listdir(sub):
                            if e2.endswith(".app"):
                                found.add(e2[:-4])
                    except OSError:
                        pass
    return sorted(found, key=str.lower)


def _token_path():
    return os.path.join(cli.overwatch_home(), "pair.json")


def pair_token():
    """This install's pairing secret, made once and kept.

    WHY THERE IS ONE AT ALL, and it is not really about GitHub Pages.
    /api/apps took a POST with no origin check and no secret, on a port every
    program on the machine can reach -- including a browser. A page on any
    website could POST to 127.0.0.1:8730 with Content-Type: text/plain, which
    is a CORS "simple request" and needs no preflight: the browser refuses to
    let the attacker READ the reply, and the write lands anyway. That is a
    stranger choosing which programs a tap on the desk starts.

    Loopback was never the protection it looked like. A token is.

    Stable across restarts because a QR printed on the panel names it -- one
    minted per boot would turn every restart into a re-pairing.
    """
    p = _token_path()
    try:
        with open(p, encoding="utf-8") as f:
            t = json.load(f).get("token")
        if isinstance(t, str) and len(t) >= 32:
            return t
    except (OSError, ValueError, AttributeError):
        pass
    t = secrets.token_hex(16)
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        fd = os.open(p + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"token": t}, f)
        os.replace(p + ".tmp", p)
    except OSError as e:
        # A token we cannot store still protects this run; it just means the
        # next restart needs re-pairing. Better than refusing to serve.
        print("[widgets] could not store the pairing token: %s" % e,
              file=sys.stderr)
    return t


def daemon_state():
    """What to tell the page about the daemon.

    `where` is the honest part. Served from inside the daemon there is
    nothing to start and the button would be a lie, so the page is told so
    and hides it.
    """
    if IN_DAEMON:
        return {"running": True, "here": True,
                "detail": "Running - this page is part of it."}
    if cli.daemon_running():
        # The pid is for the message only. The LOCK is what decided the
        # answer, and it is held by a daemon whose pid file this page may
        # not be able to find -- a binary run in place out of a build
        # directory writes it beside itself.
        pid = cli.daemon_alive()
        return {"running": True, "here": False,
                "detail": "Running%s." % (" (pid %d)" % pid if pid else "")}
    return {"running": False, "here": False,
            "detail": "Not running. The panel is not being fed."}


def start_daemon():
    """Launch the bridge and wait for it to say it is up.

    DETACHED, and deliberately so: this page is usually a short-lived
    `python3 -m pc.webconfig`, and a daemon started as its child would die
    with the tab that started it. start_new_session takes it out of this
    process group so a Ctrl-C here cannot reach it.

    No arguments are taken from the request. The command comes from
    cli.daemon_start_command() and nothing the browser sends can influence
    it -- this endpoint starts ONE known program or nothing at all.
    """
    if daemon_state()["running"]:
        return True, "Already running."
    cmd, cwd = cli.daemon_start_command()
    log = os.path.join(cli.overwatch_home(), "bridge.log")
    try:
        os.makedirs(cli.overwatch_home(), exist_ok=True)
        fh = open(log, "a", encoding="utf-8", errors="replace")
    except OSError as e:
        return False, "could not open %s: %s" % (log, e)
    try:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL,
                                cwd=cwd, **DETACHED)
    except OSError as e:
        fh.close()
        return False, "could not run %s: %s" % (cmd[0], e)
    finally:
        # Popen dup'd the descriptor; this copy is not ours to hold open.
        try:
            fh.close()
        except OSError:
            pass

    # Do not return on a successful spawn. The daemon can be dead a second
    # later -- no pyserial, a serial port another process already holds --
    # and "Started" followed by nothing happening is the least useful thing
    # this could say.
    #
    # Two signals, and the CHILD HANDLE is the authoritative one. The pid
    # file is how you find a daemon somebody else started; for the one we
    # just started, proc knows. Waiting on the pid file alone would have
    # reported a 12-second timeout for a daemon that came up perfectly but
    # wrote its pid somewhere pid_paths() does not sweep -- and, worse,
    # would have sat out the whole 12 seconds before admitting to a crash
    # that happened in the first one.
    deadline = time.time() + START_WAIT_S
    while time.time() < deadline:
        pid = cli.daemon_alive()
        if pid:
            return True, "Started (pid %d)." % pid
        if proc.poll() is not None:
            return False, ("it exited immediately (status %s) - see %s"
                           % (proc.returncode, log))
        time.sleep(0.4)
    if proc.poll() is None:
        return True, "Started (pid %d)." % proc.pid
    return False, ("it did not come up within %ds - see %s"
                   % (int(START_WAIT_S), log))


PAGE = """<!doctype html><meta charset=utf-8>
<title>Overwatch</title>
<style>
 body{font:16px/1.6 -apple-system,system-ui,sans-serif;background:#14171c;
      color:#e8ecf2;margin:0;height:100vh;display:grid;place-items:center;
      text-align:center;padding:24px}
 main{max-width:420px}
 h1{font-size:20px;font-weight:600;margin:0 0 8px}
 p{color:#8a94a4;margin:0 0 22px;font-size:15px}
 a.go{display:inline-block;background:#d9694a;color:#14171c;font-weight:600;
      text-decoration:none;padding:12px 22px;border-radius:9px;font-size:15px}
 small{display:block;margin-top:20px;color:#6e7889;font-size:12.5px}
</style>
<main>
  <h1>Overwatch is running</h1>
  <p>Everything else happens on the setup page. This link pairs it with
     this computer \u2014 it only works from here.</p>
  <a class=go id=go href="#">Open the setup page</a>
  <small id=note>pairing\u2026</small>
</main>
<script>
fetch('/api/pair').then(r=>r.json()).then(d=>{
  document.getElementById('go').href = d.link;
  document.getElementById('note').textContent =
    'It will remember this computer. Keep the link to yourself.';
}).catch(e=>{
  document.getElementById('note').textContent = 'Could not pair: ' + e;
});
</script>"""


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        """Answer an allowed origin, and only by name.

        Vary: Origin because the answer differs per request and a cache that
        forgot would hand one origin's permission to another.
        """
        origin = self.headers.get("Origin")
        if _origin_ok(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers",
                             "content-type, " + TOKEN_HEADER.lower())
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            # Chrome is tightening requests from public origins to local
            # addresses. Without this the preflight starts failing on its
            # own schedule, and the page breaks for reasons nothing here
            # will explain.
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def _authed(self):
        """Is this request allowed to act?

        Same-origin requests carry no Origin header and come from the page
        this daemon serves itself; anything with an Origin is off-machine
        and needs the token. Checked with compare_digest so a wrong guess
        cannot be narrowed down by timing it.
        """
        if not self.headers.get("Origin"):
            return True
        got = self.headers.get(TOKEN_HEADER, "")
        return secrets.compare_digest(got, pair_token())

    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/state":
            if not self._authed():
                return self._send(403, json.dumps({"error": "not paired"}))
            return self._send(200, json.dumps({
                "apps": widgets.load_apps(),
                "installed": installed_apps(),
                "icons": list(widgets.ICON_KEYS),
            }))
        if self.path == "/api/pair":
            # SAME-ORIGIN ONLY, and that is the whole point: this hands out
            # the secret, so it answers the page this daemon serves itself
            # and nothing that arrives with an Origin. A cross-origin caller
            # asking for the token is either the page that already has it or
            # an attacker who does not.
            if self.headers.get("Origin"):
                return self._send(403, json.dumps({"error": "same-origin only"}))
            return self._send(200, json.dumps({
                "token": pair_token(),
                "app": APP_URL,
                "link": "%s#t=%s" % (APP_URL, pair_token()),
            }))
        if self.path == "/api/daemon":
            return self._send(200, json.dumps(daemon_state()))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path == "/api/daemon/start":
            # POST, not GET: it starts a process, and a GET would fire on a
            # bookmark, a prefetch or a refresh.
            ok, detail = start_daemon()
            return self._send(200 if ok else 500,
                              json.dumps({"ok": ok, "detail": detail}))
        if self.path != "/api/apps":
            return self._send(404, json.dumps({"error": "not found"}))
        if not self._authed():
            return self._send(403, json.dumps({"ok": False,
                                               "error": "not paired"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            apps = json.loads(self.rfile.read(n).decode("utf-8"))
            if not isinstance(apps, list):
                raise ValueError("expected a list")
            # Names only, and only as many as the panel has tiles. The board
            # sends a SLOT NUMBER and the daemon turns it into a program, so
            # what lands here decides what a tap can start - it is checked
            # rather than trusted, even from loopback.
            apps = [a for a in apps if isinstance(a, str)][:widgets.SLOTS]
            apps += [""] * (widgets.SLOTS - len(apps))
            path = widgets._config_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(apps, fh, indent=2)
            os.replace(tmp, path)          # atomic: the daemon may be reading
            self._send(200, json.dumps({"ok": True}))
        except Exception as e:
            self._send(400, json.dumps({"ok": False, "error": str(e)}))

    def log_message(self, *a):
        pass                                # no request log on the console


def serve():
    srv = HTTPServer((HOST, PORT), Handler)
    print("launcher config on http://%s:%d  (Ctrl-C to stop)" % (HOST, PORT))
    srv.serve_forever()


URL = "http://%s:%d" % (HOST, PORT)


def serve_background():
    """Run the config page alongside the daemon. Returns the server, or None.

    None rather than an exception on a bound port: the usual cause is a second
    daemon already serving this page, and the launcher's whole job is to keep
    the board fed. Taking the daemon down over a config page nobody has opened
    would trade the product for a convenience.

    Loopback only, inherited from HOST -- the page has no authentication and
    edits what the machine will launch, so it must not be reachable off-box.
    """
    global IN_DAEMON
    try:
        srv = HTTPServer((HOST, PORT), Handler)
    except OSError as e:
        print("[widgets] config page not started: %s" % e, file=sys.stderr)
        return None
    IN_DAEMON = True      # only the daemon calls this; see daemon_state()
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    # Daemon thread: this should never be the reason the process refuses to
    # exit. serve_forever() has no timeout and would otherwise outlive the
    # bridge it was started for.
    t.start()
    print("[widgets] config page on %s" % URL, file=sys.stderr)
    return srv


if __name__ == "__main__":
    serve()
