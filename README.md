# ESP32_WoMo_gas_level_2_mqtt
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
