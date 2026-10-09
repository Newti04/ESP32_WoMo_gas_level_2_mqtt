from machine import Pin
import elescale
import utime

clkDev = Pin(17, Pin.OUT , Pin.PULL_DOWN)
dataDev = Pin(16, Pin.IN , Pin.PULL_UP)

scaleObj = elescale.EleScale(clkDev, dataDev, 20.5)
print("elescale inited!")

while True:
    weight = scaleObj.getWeight()
    print("%.2f g"%weight)
    utime.sleep(1)
