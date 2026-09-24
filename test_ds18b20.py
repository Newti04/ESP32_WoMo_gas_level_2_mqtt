import time
import machine
import onewire
import ds18x20

# Pin definieren
ds_pin = machine.Pin(4)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))

print("Scanne OneWire-Bus...")
roms = ds_sensor.scan()
print("Gefundene Sensor-Adressen:", roms)

if roms:
    ds_sensor.convert_temp()
    time.sleep_ms(750)
    for rom in roms:
        print("Temperatur:", ds_sensor.read_temp(rom), "°C")
else:
    print("Kein DS18B20 gefunden! Verkabelung und Pull-Up-Widerstand prüfen.")

