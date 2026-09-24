# --- SYSTEM-STEUERUNG ---
ZWEI_WAAGEN_AKTIV = True  # Setze auf True, sobald die 2. Waage physisch angeschlossen ist!

# --- NETZWERK & MQTT ---
WIFI_SSID = "<YOURSSID>"
WIFI_PASS = "<PASSWORT<"
MQTT_BROKER = "192.168.xxx.yyy"
MQTT_TOPIC = "WoMo/gaslevel"
CLIENT_ID = "esp32_gaslevel"

# --- PIN-BELEGUNG (ESP32) ---
# HX711 Wägezelle 1 (Flasche 1)
HX711_DOUT_1 = 16
HX711_SCK_1 = 17

# HX711 Wägezelle 2 (Flasche 2) - NEU!
HX711_DOUT_2 = 32
HX711_SCK_2 = 27

# BMP280 I2C-Bus
BMP280_SDA = 21
BMP280_SCL = 22

# DS18B20 OneWire Sensor
DS18B20_PIN = 4  # Neuer Pin für den DS18B20

# --- GASFLASCHEN PARAMETER & KALIBRIERUNG ---
SCALE_FACTOR_1 = 420.0
BOTTLE_TARE_1 = 11.8    # Tara Flasche 1 (in kg)
GAS_MAX_NET_1 = 11.0    # Maximaler Inhalt Flasche 1

SCALE_FACTOR_2 = 420.0  # NEU!
BOTTLE_TARE_2 = 11.8    # Tara Flasche 2 (in kg)
GAS_MAX_NET_2 = 11.0    # Maximaler Inhalt Flasche 2

