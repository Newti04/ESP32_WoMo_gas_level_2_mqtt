"""WoMo Gasfuellstand - ESP32 (WROOM-32), MicroPython >= 1.20

2x HX711 (Gasflaschen), BMP280 (Gaskasten), DS18B20 (aussen)
WLAN mit Hotspot-Fallback, asynchroner Webserver, MQTT-Publish.
"""
import gc
import json
import time
import machine
import network
import onewire
import ds18x20
from machine import Pin, I2C

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

from hx711 import HX711
from bmp280 import BMP280

AP_SSID = "WoMo-Gas"
AP_PASS = "womo-gas"      # mind. 8 Zeichen
CFG_FILE = "config.json"
USE_WDT = True            # bei der Entwicklung ggf. auf False setzen

DEFAULTS = {
    "wifi_ssid": "", "wifi_pass": "",
    "mqtt_host": "", "mqtt_port": 1883, "mqtt_user": "", "mqtt_pass": "",
    "mqtt_client_id": "womo-gas", "mqtt_topic": "WoMo/gaslevel",
    "mqtt_interval": 60,
    "g1_empty": 5.0, "g1_fill": 11.0, "g1_offset": 0, "g1_scale": 1000.0,
    "g2_empty": 5.0, "g2_fill": 11.0, "g2_offset": 0, "g2_scale": 1000.0,
    "density": 0.51,
    "hx1_dout": 16, "hx1_sck": 17, "hx2_dout": 32, "hx2_sck": 27,
    "bmp_sda": 21, "bmp_scl": 22, "ds_pin": 4,
}

cfg = {}

data = {
    "gas1_kg": None, "gas1_l": None, "gas1_pct": None, "gas1_gross": None, "gas1_raw": None,
    "gas2_kg": None, "gas2_l": None, "gas2_pct": None, "gas2_gross": None, "gas2_raw": None,
    "box_temp": None, "pressure": None, "out_temp": None,
    "ip": "--", "mqtt": "aus",
}
MQTT_KEYS = ("gas1_l", "gas1_pct", "gas1_kg", "gas2_l", "gas2_pct", "gas2_kg",
             "box_temp", "pressure", "out_temp")

scales = [None, None]
sta = network.WLAN(network.STA_IF)
ap = network.WLAN(network.AP_IF)
FLASH = [""]


# ---------------------------------------------------------------- Konfiguration
def load_cfg():
    cfg.update(DEFAULTS)
    try:
        with open(CFG_FILE) as f:
            cfg.update(json.load(f))
    except Exception:
        pass


def save_cfg():
    with open(CFG_FILE, "w") as f:
        json.dump(cfg, f)


# ---------------------------------------------------------------- Helfer
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def to_num(s, cast=float, default=None):
    try:
        return cast(str(s).strip().replace(",", "."))
    except Exception:
        return default


def unquote(s):
    s = s.replace("+", " ")
    parts = s.split("%")
    out = bytearray(parts[0].encode())
    for p in parts[1:]:
        try:
            out.append(int(p[:2], 16))
            out.extend(p[2:].encode())
        except Exception:
            out.extend(b"%")
            out.extend(p.encode())
    try:
        return out.decode()
    except Exception:
        return ""


def parse_form(s):
    res = {}
    for pair in s.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            res[unquote(k)] = unquote(v)
    return res


def S(v):
    return "--" if v is None else str(v)


# ---------------------------------------------------------------- HTML
CSS = ("body{font-family:sans-serif;margin:0;background:#f2f4f7;color:#222}"
       "header{background:#1d4e89;padding:.6em 1em}"
       "header a{color:#fff;margin-right:1em;text-decoration:none;font-weight:bold}"
       "main{max-width:640px;margin:auto;padding:1em}"
       ".card{background:#fff;border-radius:8px;padding:1em;margin-bottom:1em;box-shadow:0 1px 3px #0003}"
       "h2{margin:.2em 0 .6em}.big{font-size:2em;font-weight:bold}"
       ".bar{background:#ddd;height:14px;border-radius:7px;overflow:hidden;margin:.4em 0}"
       ".bar div{background:#2e9e4f;height:100%}"
       "label{display:block;margin:.6em 0 .2em}"
       "input{width:100%;box-sizing:border-box;padding:.5em;font-size:1em}"
       "button{margin-top:.8em;padding:.6em 1em;font-size:1em;border:0;border-radius:6px;background:#1d4e89;color:#fff}"
       ".msg{background:#e6f4ea;padding:.6em;border-radius:6px;margin-bottom:1em}"
       ".row{display:flex;gap:.5em}.row>*{flex:1}small{color:#666}")

NAV = ('<a href="/">Status</a><a href="/config_net.html">Netzwerk</a>'
       '<a href="/config_gas.html">Gas</a><a href="/config_hw.html">Hardware</a>')


def page(title, inner, script=""):
    m = FLASH[0]
    FLASH[0] = ""
    return ('<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + title + '</title><style>' + CSS + '</style></head><body>'
            '<header>' + NAV + '</header><main>'
            + ('<div class="msg">' + esc(m) + '</div>' if m else "")
            + inner + '</main>'
            + ('<script>' + script + '</script>' if script else "")
            + '</body></html>')


def field(label, name, val, typ="text", extra=""):
    return '<label>%s</label><input type="%s" name="%s" value="%s" %s>' % (
        label, typ, name, esc(val), extra)


def page_index():
    h = ""
    for i in (1, 2):
        k = "gas%d_" % i
        pct = data[k + "pct"] or 0
        h += ('<div class="card"><h2>Gasflasche %d</h2>'
              '<div class="big"><span id="%sl">%s</span> l &nbsp; <span id="%spct">%s</span> %%</div>'
              '<div class="bar"><div id="bar%d" style="width:%d%%"></div></div>'
              '<small><span id="%skg">%s</span> kg Gas</small></div>') % (
            i, k, S(data[k + "l"]), k, S(data[k + "pct"]), i, pct, k, S(data[k + "kg"]))
    h += ('<div class="card"><h2>Umgebung</h2>'
          '<p>Gaskasten: <b><span id="box_temp">%s</span> &deg;C</b></p>'
          '<p>Luftdruck: <b><span id="pressure">%s</span> hPa</b></p>'
          '<p>Au&szlig;en: <b><span id="out_temp">%s</span> &deg;C</b></p></div>') % (
        S(data["box_temp"]), S(data["pressure"]), S(data["out_temp"]))
    h += ('<div class="card"><small>WLAN: <span id="ip">%s</span><br>'
          'MQTT: <span id="mqtt">%s</span></small></div>') % (esc(data["ip"]), esc(data["mqtt"]))
    js = ("async function u(){try{const d=await (await fetch('/api/data')).json();"
          "for(const k in d){const e=document.getElementById(k);if(e)e.textContent=d[k]===null?'--':d[k]}"
          "for(const i of [1,2]){const b=document.getElementById('bar'+i);"
          "if(b)b.style.width=(d['gas'+i+'_pct']||0)+'%'}}catch(e){}}"
          "setInterval(u,3000);u();")
    return page("Gasf&uuml;llstand", h, js)


def page_net():
    h = '<form method="post"><div class="card"><h2>WLAN</h2>'
    h += field("SSID", "wifi_ssid", cfg["wifi_ssid"], "text", 'list="nets" autocomplete="off"')
    h += '<datalist id="nets"></datalist>'
    h += '<button type="button" id="sb" onclick="scan()">Netzwerke suchen</button>'
    h += field("Passwort", "wifi_pass", "", "password", 'placeholder="(unverändert)"')
    h += '</div><div class="card"><h2>MQTT</h2>'
    h += field("Server", "mqtt_host", cfg["mqtt_host"])
    h += field("Port", "mqtt_port", cfg["mqtt_port"], "number")
    h += field("Benutzer", "mqtt_user", cfg["mqtt_user"])
    h += field("Passwort", "mqtt_pass", "", "password", 'placeholder="(unverändert)"')
    h += field("Client-ID", "mqtt_client_id", cfg["mqtt_client_id"])
    h += field("Topic (JSON mit allen Messwerten)", "mqtt_topic", cfg["mqtt_topic"])
    h += field("Intervall (Sekunden, min. 5)", "mqtt_interval", cfg["mqtt_interval"], "number", 'min="5"')
    h += '<button>Speichern &amp; Neustart</button></div></form>'
    js = ("async function scan(){const b=document.getElementById('sb');b.textContent='Suche...';"
          "try{const l=await (await fetch('/api/scan')).json();"
          "const dl=document.getElementById('nets');dl.innerHTML='';"
          "l.forEach(n=>{const o=document.createElement('option');o.value=n;dl.appendChild(o)});}catch(e){}"
          "b.textContent='Netzwerke suchen'}")
    return page("Netzwerk", h, js)


def page_gas():
    h = '<form method="post"><div class="card"><h2>Gasflaschen</h2>'
    for i in (1, 2):
        k = "g%d_" % i
        h += '<h3>Flasche %d</h3><div class="row"><div>%s</div><div>%s</div></div>' % (
            i,
            field("Leergewicht (kg)", k + "empty", cfg[k + "empty"], "number", 'step="0.01" min="0"'),
            field("Füllmenge (kg)", k + "fill", cfg[k + "fill"], "number", 'step="0.01" min="0"'))
    h += field("Dichte Flüssiggas (kg/l, für Liter-Anzeige)", "density", cfg["density"],
               "number", 'step="0.001" min="0.1"')
    h += '<button>Speichern</button></div></form>'
    for i in (1, 2):
        k = "g%d_" % i
        h += ('<div class="card"><h2>Waage %d kalibrieren</h2>'
              '<p>Rohwert: <b>%s</b> &middot; Gesamtgewicht: <b>%s kg</b><br>'
              '<small>Tara-Offset %s &middot; Scalefaktor %s</small></p>'
              '<small>1. Waage unbelastet &rarr; Tara. 2. Bekanntes Gewicht auflegen, '
              'Gewicht eingeben &rarr; Scalefaktor.</small>') % (
            i, S(data["gas%d_raw" % i]), S(data["gas%d_gross" % i]),
            cfg[k + "offset"], round(cfg[k + "scale"], 2))
        h += ('<form method="post"><input type="hidden" name="action" value="tare%d">'
              '<button>Tara</button></form>') % i
        h += ('<form method="post"><input type="hidden" name="action" value="scale%d">%s'
              '<button>Scalefaktor berechnen</button></form></div>') % (
            i, field("Referenzgewicht (kg)", "ref", "", "number", 'step="0.01" required'))
    return page("Gas", h)


def page_hw():
    h = ('<form method="post"><div class="card"><h2>Pin-Zuordnung (GPIO)</h2>'
         '<small>&Auml;nderungen werden nach einem Neustart aktiv.</small>')
    for title, items in (
        ("HX711 Waage 1", (("DOUT", "hx1_dout"), ("SCK", "hx1_sck"))),
        ("HX711 Waage 2", (("DOUT", "hx2_dout"), ("SCK", "hx2_sck"))),
        ("BMP280 (I2C)", (("SDA", "bmp_sda"), ("SCL", "bmp_scl"))),
        ("DS18B20", (("Pin", "ds_pin"),)),
    ):
        h += "<h3>%s</h3><div class=\"row\">" % title
        for lab, key in items:
            h += "<div>%s</div>" % field(lab, key, cfg[key], "number", 'min="0" max="39"')
        h += "</div>"
    h += '<button>Speichern &amp; Neustart</button></div></form>'
    return page("Hardware", h)


# ---------------------------------------------------------------- Sensoren
def calc_scale(i, raw):
    k = "g%d_" % i
    data["gas%d_raw" % i] = None if raw is None else int(raw)
    if raw is None:
        for s in ("kg", "l", "pct", "gross"):
            data["gas%d_%s" % (i, s)] = None
        return
    sc = cfg[k + "scale"]
    gross = (raw - cfg[k + "offset"]) / sc if sc else 0
    gas = max(0.0, gross - cfg[k + "empty"])
    dens = cfg["density"] or 0.51
    fill = cfg[k + "fill"]
    data["gas%d_gross" % i] = round(gross, 2)
    data["gas%d_kg" % i] = round(gas, 2)
    data["gas%d_l" % i] = round(gas / dens, 1)
    data["gas%d_pct" % i] = int(min(100, max(0, gas / fill * 100))) if fill > 0 else None


async def scale_task(i):
    while True:
        hx = scales[i - 1]
        if hx is None:
            calc_scale(i, None)
            await asyncio.sleep(5)
            continue
        try:
            raw = await hx.read_avg(5, 2000)
        except Exception:
            raw = None
        calc_scale(i, raw)
        await asyncio.sleep(1)


async def env_task():
    bmp = None
    ds = None
    roms = []
    try:
        ds = ds18x20.DS18X20(onewire.OneWire(Pin(cfg["ds_pin"])))
    except Exception as e:
        print("DS18B20 Init:", e)
    while True:
        if bmp is None:
            try:
                bmp = BMP280(I2C(0, scl=Pin(cfg["bmp_scl"]), sda=Pin(cfg["bmp_sda"]), freq=100000))
            except Exception:
                bmp = None
        if bmp is not None:
            try:
                t, p = bmp.read()
                data["box_temp"] = round(t, 1)
                data["pressure"] = round(p, 1) if p else None
            except Exception:
                bmp = None
                data["box_temp"] = None
                data["pressure"] = None
        else:
            data["box_temp"] = None
            data["pressure"] = None
        if ds is not None:
            try:
                if not roms:
                    roms = ds.scan()
                if roms:
                    ds.convert_temp()
                    await asyncio.sleep_ms(800)
                    t = ds.read_temp(roms[0])
                    if t != 85.0:   # 85.0 = Power-on-Wert, ungueltig
                        data["out_temp"] = round(t, 1)
                else:
                    data["out_temp"] = None
            except Exception:
                roms = []
                data["out_temp"] = None
        await asyncio.sleep(2)


# ---------------------------------------------------------------- WLAN
def start_ap():
    try:
        ap.active(True)
        ap.config(essid=AP_SSID, password=AP_PASS, authmode=network.AUTH_WPA_WPA2_PSK)
    except Exception as e:
        print("AP:", e)


def stop_ap():
    try:
        ap.active(False)
    except Exception:
        pass


def wifi_connect():
    try:
        sta.disconnect()
    except Exception:
        pass
    try:
        sta.connect(cfg["wifi_ssid"], cfg["wifi_pass"])
    except Exception as e:
        print("WLAN:", e)


async def wifi_task():
    sta.active(True)
    has_cfg = bool(cfg["wifi_ssid"])
    if has_cfg:
        wifi_connect()
    else:
        start_ap()
    offline = 0
    while True:
        if not has_cfg:
            data["ip"] = "Hotspot " + AP_SSID + " (192.168.4.1)"
        elif sta.isconnected():
            offline = 0
            data["ip"] = sta.ifconfig()[0]
            if ap.active():
                stop_ap()
        else:
            offline += 1
            data["ip"] = "nicht verbunden"
            if offline % 20 == 0:
                wifi_connect()          # erneut versuchen
            if offline >= 20 and not ap.active():
                start_ap()              # Fallback-Hotspot
            if ap.active():
                data["ip"] = "Hotspot " + AP_SSID + " (192.168.4.1)"
        await asyncio.sleep(1)


# ---------------------------------------------------------------- MQTT (Publish, ohne Zusatzmodule)
def _s(x):
    b = x.encode() if isinstance(x, str) else x
    return len(b).to_bytes(2, "big") + b


def _rl(n):
    out = bytearray()
    while True:
        d = n % 128
        n //= 128
        if n:
            d |= 0x80
        out.append(d)
        if not n:
            break
    return bytes(out)


async def mqtt_publish(payload):
    host = cfg["mqtt_host"]
    port = int(cfg["mqtt_port"])
    flags = 0x02
    body = _s("MQTT") + b"\x04"
    user = cfg["mqtt_user"]
    pw = cfg["mqtt_pass"]
    if user:
        flags |= 0x80
        if pw:
            flags |= 0x40
    body += bytes([flags]) + (30).to_bytes(2, "big") + _s(cfg["mqtt_client_id"] or "womo-gas")
    if user:
        body += _s(user)
        if pw:
            body += _s(pw)
    r, w = await asyncio.wait_for(asyncio.open_connection(host, port), 8)
    try:
        w.write(b"\x10" + _rl(len(body)) + body)
        await w.drain()
        resp = await asyncio.wait_for(r.readexactly(4), 8)
        if resp[0] != 0x20 or resp[3] != 0:
            raise OSError("CONNACK %d" % resp[3])
        pub = _s(cfg["mqtt_topic"]) + payload.encode()
        w.write(b"\x31" + _rl(len(pub)) + pub)   # QoS 0, retain
        w.write(b"\xe0\x00")
        await w.drain()
    finally:
        w.close()
        try:
            await w.wait_closed()
        except Exception:
            pass


async def mqtt_task():
    while True:
        wait = max(5, to_num(cfg["mqtt_interval"], int, 60))
        if not cfg["mqtt_host"]:
            data["mqtt"] = "aus"
            wait = 5
        elif not sta.isconnected():
            data["mqtt"] = "kein WLAN"
            wait = 5
        else:
            try:
                payload = json.dumps({k: data[k] for k in MQTT_KEYS})
                await mqtt_publish(payload)
                data["mqtt"] = "OK"
            except Exception as e:
                data["mqtt"] = "Fehler: " + str(e)
                wait = min(wait, 10)    # schneller erneut verbinden
        gc.collect()
        await asyncio.sleep(wait)


# ---------------------------------------------------------------- Webserver
async def reboot_later():
    await asyncio.sleep(1.5)
    machine.reset()


async def gas_action(form):
    a = form.get("action", "")
    n = a[-1:]
    if n not in ("1", "2"):
        return "Unbekannte Aktion"
    hx = scales[int(n) - 1]
    if hx is None:
        return "HX711 %s nicht initialisiert" % n
    raw = await hx.read_avg(10, 3000)
    if raw is None:
        return "HX711 %s antwortet nicht (Verkabelung prüfen)" % n
    k = "g" + n + "_"
    if a.startswith("tare"):
        cfg[k + "offset"] = int(raw)
        save_cfg()
        return "Tara für Waage %s gesetzt (Rohwert %d)" % (n, int(raw))
    ref = to_num(form.get("ref"))
    if not ref or ref <= 0:
        return "Bitte ein Referenzgewicht (kg) größer 0 eingeben"
    counts = raw - cfg[k + "offset"]
    if abs(counts) < 100:
        return "Kein Unterschied zur Tara erkannt - bitte Referenzgewicht auflegen"
    cfg[k + "scale"] = counts / ref
    save_cfg()
    return "Scalefaktor Waage %s: %.1f" % (n, cfg[k + "scale"])


def ok(body, ctype="text/html; charset=utf-8"):
    return ("200 OK", ctype, body, "")


def redirect(loc):
    return ("303 See Other", "text/plain", "", "Location: %s\r\n" % loc)


def restart_page(text):
    return ok(page("Neustart", '<div class="card"><h2>Gespeichert</h2><p>%s</p>'
                   '<p>Das Ger&auml;t startet neu. Danach ist die Seite wieder erreichbar '
                   '(bei neuen WLAN-Daten unter der neuen IP-Adresse bzw. &uuml;ber den Hotspot).</p></div>' % text))


async def route(method, path, form):
    path = path.split("?")[0]
    if path in ("/", "/index.html"):
        return ok(page_index())
    if path == "/api/data":
        return ok(json.dumps(data), "application/json")
    if path == "/api/scan":
        nets = []
        try:
            for r in sta.scan():
                s = r[0].decode()
                if s:
                    nets.append(s)
        except Exception:
            pass
        return ok(json.dumps(sorted(set(nets))), "application/json")

    if path == "/config_net.html":
        if method == "POST":
            old = cfg["wifi_ssid"]
            cfg["wifi_ssid"] = form.get("wifi_ssid", "").strip()
            if form.get("wifi_pass") or cfg["wifi_ssid"] != old:
                cfg["wifi_pass"] = form.get("wifi_pass", "")
            cfg["mqtt_host"] = form.get("mqtt_host", "").strip()
            cfg["mqtt_port"] = to_num(form.get("mqtt_port"), int, 1883)
            cfg["mqtt_user"] = form.get("mqtt_user", "")
            if form.get("mqtt_pass") or not cfg["mqtt_user"]:
                cfg["mqtt_pass"] = form.get("mqtt_pass", "")
            cfg["mqtt_client_id"] = form.get("mqtt_client_id", "").strip() or "womo-gas"
            cfg["mqtt_topic"] = form.get("mqtt_topic", "").strip() or "WoMo/gaslevel"
            cfg["mqtt_interval"] = max(5, to_num(form.get("mqtt_interval"), int, 60))
            save_cfg()
            asyncio.create_task(reboot_later())
            return restart_page("Netzwerk-Einstellungen gespeichert.")
        return ok(page_net())

    if path == "/config_gas.html":
        if method == "POST":
            if "action" in form:
                FLASH[0] = await gas_action(form)
            else:
                for k in ("g1_empty", "g1_fill", "g2_empty", "g2_fill", "density"):
                    v = to_num(form.get(k))
                    if v is not None and v >= 0:
                        cfg[k] = v
                save_cfg()
                FLASH[0] = "Gespeichert"
            return redirect("/config_gas.html")
        return ok(page_gas())

    if path == "/config_hw.html":
        if method == "POST":
            keys = ("hx1_dout", "hx1_sck", "hx2_dout", "hx2_sck", "bmp_sda", "bmp_scl", "ds_pin")
            vals = {}
            for k in keys:
                v = to_num(form.get(k), int)
                if v is None or v < 0 or v > 39:
                    FLASH[0] = "Ungültiger Pin für " + k + " (0-39)"
                    return redirect("/config_hw.html")
                vals[k] = v
            cfg.update(vals)
            save_cfg()
            asyncio.create_task(reboot_later())
            return restart_page("Pin-Zuordnung gespeichert.")
        return ok(page_hw())

    return ("404 Not Found", "text/plain", "Nicht gefunden", "")


async def send(w, status, ctype, body, hdr):
    b = body.encode() if isinstance(body, str) else body
    w.write(("HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
             "Connection: close\r\nCache-Control: no-store\r\n%s\r\n"
             % (status, ctype, len(b), hdr)).encode())
    if b:
        w.write(b)
    await w.drain()


async def handle(r, w):
    try:
        line = await asyncio.wait_for(r.readline(), 5)
        if not line:
            return
        parts = line.decode().split(" ")
        method, path = parts[0], parts[1]
        clen = 0
        while True:
            h = await asyncio.wait_for(r.readline(), 5)
            if h in (b"\r\n", b"\n", b""):
                break
            if h.lower().startswith(b"content-length:"):
                clen = int(h.split(b":")[1])
        form = {}
        if clen:
            if clen > 2048:
                await send(w, "413 Payload Too Large", "text/plain", "zu gross", "")
                return
            body = await asyncio.wait_for(r.readexactly(clen), 5)
            form = parse_form(body.decode())
        status, ctype, resp, hdr = await route(method, path, form)
        await send(w, status, ctype, resp, hdr)
    except Exception as e:
        print("HTTP:", e)
    finally:
        try:
            w.close()
            await w.wait_closed()
        except Exception:
            pass
        gc.collect()


# ---------------------------------------------------------------- Start
async def main():
    load_cfg()
    for i, (d, s) in enumerate((("hx1_dout", "hx1_sck"), ("hx2_dout", "hx2_sck"))):
        try:
            scales[i] = HX711(cfg[d], cfg[s])
        except Exception as e:
            print("HX711 %d:" % (i + 1), e)
    asyncio.create_task(wifi_task())
    asyncio.create_task(scale_task(1))
    asyncio.create_task(scale_task(2))
    asyncio.create_task(env_task())
    asyncio.create_task(mqtt_task())
    await asyncio.start_server(handle, "0.0.0.0", 80)
    wdt = machine.WDT(timeout=60000) if USE_WDT else None
    while True:
        if wdt:
            wdt.feed()
        await asyncio.sleep(5)


try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
