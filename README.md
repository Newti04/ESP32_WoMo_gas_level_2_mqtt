# ESP32_WoMo_gas_level_2_mqtt

Hardware:

1x ESP32 (Wroom-32)

2x hx711 (HX711_DOUT_1 = 16, HX711_SCK_1 = 17, HX711_DOUT_2 = 32, HX711_SCK_2 = 27)

1x BMP280 (BMP280_SDA = 21, BMP280_SCL = 22)

1x DS18B20 (DS18B20_PIN = 4)

1x 470kOhm Widerstand (PullUp PIN 4)

Software:
Micropython mit asyncronem webserver, mqtt client

Der ESP32 soll einen WLAN hotspot haben, um die ersten WLAN Einstellungen vornehmen zu können und falls keine WLAN Verbindung zustande kommt.
Das WLAN und der Mqtt Client sollen sich wieder verbinden, falls die Netzwerk Verbindung unterbrochen war.
Die Webserver läuft asyncron, damit die Website jederzeit erreichbar ist.

Der Webserver hat folgende Seiten:
index.hml
Diese zeigt den aktuellen Füllstand der beiden Gasflaschen in Liter und Prozent (Daten von den beiden hx711),
die Gaskasten Temperatur und Luftdruck (BMP 280),
die Außentemperatur (DS18B20)

config_net.html
Einstellungen für das 
WLAN, 
MQTT Server, 
Topics: WoMo/gaslevel mit json aller Messwerte
Zeitinterval für Aktualisierung der Werte zum Mqtt Server.

config_gas.html
Leergewicht und Füllmenge der Gasflaschen,
sowie Knöpfe für Tara und Scalefaktor mit Eingabefeld des Referenzgewichtes.

config_hw.html
Die PIN-Zuordnung für 
die beiden hx711, 
den BMP280 und 
den DS18B20



# Instalation
Micropython script to get the weight with two scales from gas bottles for hardware ESP32, hx711, bmp280 and DS18B20 for external temperature. The measurements are showed on a local website and published to a mqtt server.


Installation:

import network
st = network.WLAN(network.STA_IF)
st.active(True)
st.connect('yourSSID','password')
import mip

mip.install('github:Newti04/ESP32_WoMo_gas_level_2_mqttSP32_WoMo_gas_level_2_mqtt/bmp180.py', '/')
mip.install('github:Newti04/ESP32_WoMo_gas_level_2_mqttSP32_WoMo_gas_level_2_mqtt/bmp280.py', '/')
mip.install('github:Newti04/ESP32_WoMo_gas_level_2_mqttSP32_WoMo_gas_level_2_mqtt/config.py', '/')
mip.install('github:Newti04/ESP32_WoMo_gas_level_2_mqttSP32_WoMo_gas_level_2_mqtt/hx711.py', '/')
mip.install('github:SergeyPiskunov/micropython-hx711/hx711.py', '/')
mip.install('github:Newti04/ESP32_WoMo_gas_level_2_mqttSP32_WoMo_gas_level_2_mqtt/index.html', '/')
mip.install('github:Newti04/ESP32_WoMo_gas_level_2_mqttSP32_WoMo_gas_level_2_mqtt/main.py', '/')
mip.install('github:Newti04/ESP32_WoMo_gas_level_2_mqttSP32_WoMo_gas_level_2_mqtt/test_bmp280.py', '/')
mip.install('github:Newti04/ESP32_WoMo_gas_level_2_mqttSP32_WoMo_gas_level_2_mqtt/test_ds18b20.py', '/')
import main

https://github.com/SergeyPiskunov/micropython-hx711
