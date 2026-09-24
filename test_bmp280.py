from machine import Pin, I2C
import config
i2c = I2C(0, sda=Pin(config.BMP280_SDA), scl=Pin(config.BMP280_SCL), freq=100000)
print(f"i2c sda={config.BMP280_SDA}, scl={config.BMP280_SCL}")
print("Scanne I2C-Bus...")
devices = i2c.scan()
print("Gefundene I2C-Geräte (Dezimal):", devices)
print("Gefundene I2C-Geräte (Hex):", [hex(d) for d in devices])
