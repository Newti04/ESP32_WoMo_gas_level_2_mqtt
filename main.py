import network
import time
import ujson
import usocket as socket
import select
from machine import Pin, I2C
from umqtt.simple import MQTTClient
from hx711 import HX711
from bmp280 import BMP280
import onewire
import ds18x20

import config

# --- HELPER STORAGE LOGIK ---
def load_val(file, default):
    try:
        with open(file, "r") as f: return float(f.read().strip()) if "." in f.read() else int(f.read().strip())
    except: return default

def save_val(file, val):
    try:
        with open(file, "w") as f: f.write(str(val))
    except: pass

scale1 = load_val("scale1.txt", config.SCALE_FACTOR_1)
scale2 = load_val("scale2.txt", config.SCALE_FACTOR_2)
offset1 = int(load_val("tare1.txt", 0))
offset2 = int(load_val("tare2.txt", 0))

latest_data = {
    "weight_1": 0.0, "gasweight_1": 0.0, "level_1": 0.0, "scale_factor_1": scale1,
    "weight_2": 0.0, "gasweight_2": 0.0, "level_2": 0.0, "scale_factor_2": scale2,
    "temperature": 0.0, "temperature_ds18b20": 0.0, "pressure": 0.0
}

# --- BMP280 INITIALISIERUNG ---
i2c = I2C(0, sda=Pin(config.BMP280_SDA), scl=Pin(config.BMP280_SCL), freq=100000)
try: bmp_sensor = BMP280(i2c)
except: bmp_sensor = None

# --- DS18B20 INITIALISIERUNG ---
try:
    ds_pin = Pin(config.DS18B20_PIN)
    ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
    roms = ds_sensor.scan()
except: roms = []

# sensor1 Setup (Immer aktiv)
sensor1 = HX711(d_out=config.HX711_DOUT_1, pd_sck=config.HX711_SCK_1)
sensor1.set_scale(scale1)
sensor1.OFFSET = offset1

# sensor2 Setup (Nur wenn physisch vorhanden!)
sensor2 = None
if config.ZWEI_WAAGEN_AKTIV:
    sensor2 = HX711(d_out=config.HX711_DOUT_2, pd_sck=config.HX711_SCK_2)
    sensor2.set_scale(scale2)
    sensor2.OFFSET = offset2
    print("[SYSTEM] Software für 2. Waage aktiviert.")
else:
    print("[SYSTEM] 2. Waage im Code deaktiviert (Schutz vor I2C-Blockade).")

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
client = None

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(('', 80))
server_socket.listen(5)
server_socket.setblocking(False)

def get_html_response():
    try:
        with open("index.html", "r") as f: return f.read().format(**latest_data)
    except Exception as e: return f"<h1>Fehler index.html</h1><p>{e}</p>"

def handle_webserver():
    global scale1, scale2
    r, w, x = select.select([server_socket], [], [], 0.02)
    if server_socket in r:
        try:
            conn, addr = server_socket.accept()
            request = conn.recv(1024).decode('utf-8')
            
            if "GET /tare" in request:
                # Prüft, welche Waage genullt werden soll (?id=1 oder ?id=2)
                if "id=1" in request:
                    sensor1.tare()
                    save_val("tare1.txt", sensor1.OFFSET)
                elif "id=2" in request:
                    sensor2.tare()
                    save_val("tare2.txt", sensor2.OFFSET)
                conn.send('HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n')
                
            elif "GET /set_scale" in request:
                try:
                    # Extrahiert Parameter aus dem URL-String
                    query = request.split("GET /set_scale?").split(" ")
                    params = query.split("&")
                    p_id = params[0].split("id=")[1]
                    p_scale = float(params[1].split("scale=")[1])
                    
                    if p_id == "1":
                        scale1 = p_scale
                        sensor1.set_scale(scale1)
                        save_val("scale1.txt", scale1)
                    elif p_id == "2":
                        scale2 = p_scale
                        sensor2.set_scale(scale2)
                        save_val("scale2.txt", scale2)
                except: pass
                conn.send('HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n')
            else:
                conn.send('HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n')
                conn.sendall(get_html_response())
            conn.close()
        except: pass

def maintain_connections():
    global client
    if not wlan.isconnected():
        wlan.connect(config.WIFI_SSID, config.WIFI_PASS)
        attempt = 0
        while not wlan.isconnected() and attempt < 5:
            time.sleep(0.5)
            attempt += 1
    if client is None and wlan.isconnected():
        try:
            client = MQTTClient(config.CLIENT_ID, config.MQTT_BROKER, keepalive=60)
            client.connect()
            return True
        except: return False
    return client is not None

def calculate_gas(total_weight, tare, max_net):
    net = total_weight - tare
    if net < 0: net = 0.0
    pct = (net / max_net) * 100
    return round(net, 2), round(100.0 if pct > 100 else pct, 1)

last_measurement = 0
MEASURE_INTERVAL = 20 

while True:
    handle_webserver()
    current_time = time.time()
    if current_time - last_measurement >= MEASURE_INTERVAL:
        last_measurement = current_time
        try:
            # 1. Waage 1 auslesen & berechnen
            tot1 = sensor1.get_units(times=5)
            g_kg1, g_pct1 = calculate_gas(tot1, config.BOTTLE_TARE_1, config.GAS_MAX_NET_1)
            
            # 2. Waage 2 auslesen (nur wenn aktiv, sonst Dummy-Werte)
            tot2 = 0.0
            g_kg2, g_pct2 = 0.0, 0.0
            if config.ZWEI_WAAGEN_AKTIV and sensor2:
                tot2 = sensor2.get_units(times=5)
                g_kg2, g_pct2 = calculate_gas(tot2, config.BOTTLE_TARE_2, config.GAS_MAX_NET_2)

            
            temp_bmp, pressure = 0.0, 0.0
            if bmp_sensor:
                try: temp_bmp, pressure = bmp_sensor.read_values()
                except: pass

            temp_ds = 0.0
            if len(roms) > 0:
                try:
                    ds_sensor.convert_temp()
                    for _ in range(15):
                        time.sleep_ms(50)
                        handle_webserver()
                    temp_ds = ds_sensor.read_temp(roms[0])
                except: pass

            # Dataset befüllen
            latest_data["weight_1"] = round(tot1, 2)
            latest_data["gasweight_1"] = g_kg1
            latest_data["level_1"] = g_pct1
            latest_data["scale_factor_1"] = scale1
            
            latest_data["weight_2"] = round(tot2, 2)
            latest_data["gasweight_2"] = g_kg2
            latest_data["level_2"] = g_pct2
            latest_data["scale_factor_2"] = scale2
            
            latest_data["temperature"] = round(temp_bmp, 1)
            latest_data["temperature_ds18b20"] = round(temp_ds, 1)
            latest_data["pressure"] = round(pressure, 1)
            
            print(f"[DATA] {ujson.dumps(latest_data)}")
            
            is_connected = maintain_connections()
            if is_connected and client:
                client.publish(config.MQTT_TOPIC, ujson.dumps(latest_data))
        except Exception as main_err:
            print("Fehler im Loop:", main_err)

