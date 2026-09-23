"""A little local page for setting the launcher's six slots.

    python3 -m pc.webconfig        then open http://127.0.0.1:8730

Editing ~/.blink/apps.json by hand works and always will; this exists because
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
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

if __package__ in (None, ""):
    # Run as `python3 pc/webconfig.py`, Python puts pc/ on the path and not
    # the project root, so `from pc import ...` cannot resolve. Put the root
    # back so the file works whether it is run as a script or as `-m`.
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pc import widgets

HOST, PORT = "127.0.0.1", 8730
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


PAGE = """<!doctype html><meta charset=utf-8>
<title>Overwatch launcher</title>
<style>
 body{font:15px/1.6 -apple-system,system-ui,sans-serif;background:#14171c;
      color:#e8ecf2;margin:0;padding:32px;display:flex;justify-content:center}
 main{width:min(560px,100%)}
 h1{font-size:19px;font-weight:600;margin:0 0 4px}
 p.sub{color:#8a94a4;margin:0 0 24px;font-size:13px}
 .slot{display:flex;align-items:center;gap:12px;margin-bottom:10px}
 .n{width:22px;color:#6e7889;font-variant-numeric:tabular-nums;font-size:13px}
 select{flex:1;padding:9px 10px;border-radius:8px;border:1px solid #2b313b;
        background:#1b1f26;color:#e8ecf2;font-size:14px}
 .ico{width:74px;font-size:11px;color:#6e7889;text-align:right}
 .ico.has{color:#3fb96b}
 button{margin-top:18px;padding:10px 18px;border-radius:8px;border:0;
        background:#d9694a;color:#14171c;font-size:14px;font-weight:600;
        cursor:pointer}
 #msg{margin-top:14px;font-size:13px;color:#3fb96b;min-height:20px}
</style>
<main>
<h1>Launcher</h1>
<p class=sub>Six slots, top-left to bottom-right, matching the grid on the panel.
Slots left empty are drawn dim and do nothing.</p>
<div id=slots></div>
<button onclick=save()>Save</button>
<div id=msg></div>
</main>
<script>
let S={};
fetch('/api/state').then(r=>r.json()).then(d=>{S=d;draw()});
function draw(){
  document.getElementById('slots').innerHTML = S.apps.map((cur,i)=>{
    const opts = ['<option value="">— empty —</option>'].concat(
      S.installed.map(a=>`<option${a===cur?' selected':''}>${a}</option>`)).join('');
    return `<div class=slot><span class=n>${i+1}</span>
            <select id=s${i} onchange=mark(${i})>${opts}</select>
            <span class="ico" id=i${i}></span></div>`;
  }).join('');
  S.apps.forEach((_,i)=>mark(i));
}
function mark(i){
  const v=document.getElementById('s'+i).value;
  const k=S.icons.find(k=>v.toLowerCase().includes(k));
  const e=document.getElementById('i'+i);
  e.textContent = v ? (k?'icon: '+k:'name only') : '';
  e.className = 'ico'+(k?' has':'');
}
function save(){
  const apps=S.apps.map((_,i)=>document.getElementById('s'+i).value);
  fetch('/api/apps',{method:'POST',body:JSON.stringify(apps)})
    .then(r=>r.json()).then(d=>{
      document.getElementById('msg').textContent =
        d.ok ? 'Saved. The panel updates within a few seconds.' : 'Failed: '+d.error;
    });
}
</script>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/state":
            return self._send(200, json.dumps({
                "apps": widgets.load_apps(),
                "installed": installed_apps(),
                "icons": list(widgets.ICON_KEYS),
            }))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/apps":
            return self._send(404, json.dumps({"error": "not found"}))
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
    try:
        srv = HTTPServer((HOST, PORT), Handler)
    except OSError as e:
        print("[widgets] config page not started: %s" % e, file=sys.stderr)
        return None
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    # Daemon thread: this should never be the reason the process refuses to
    # exit. serve_forever() has no timeout and would otherwise outlive the
    # bridge it was started for.
    t.start()
    print("[widgets] config page on %s" % URL, file=sys.stderr)
    return srv


if __name__ == "__main__":
    serve()
