from machine import Pin, I2C
from mfrc522 import MFRC522
import utime
from ssd1306 import SSD1306_I2C
from oled import Write, GFX, SSD1306_I2C
from oled.fonts import ubuntu_mono_15, ubuntu_mono_20
       
rfid_reader = MFRC522(spi_id=0,sck=2,miso=4,mosi=7,cs=5,rst=18)
WIDTH  = 128                                            # oled display width
HEIGHT = 64                                             # oled display height
 
i2c = I2C(0, scl=Pin(17), sda=Pin(16), freq=200000)       # Init I2C using pins GP8 & GP9 (default I2C0 pins)
 
display = SSD1306_I2C(WIDTH, HEIGHT, i2c)                  # Init oled display
fontSize20 = Write(display, ubuntu_mono_20)

 
 
while True:
    rfid_reader.init()
    display.fill(0)       
    fontSize20.text("RC522", 40, 0)
    display.text("Interfacing", 25, 22)
    
    (card_status, card_type) = rfid_reader.request(rfid_reader.REQIDL)
    if card_status == rfid_reader.OK:
        (card_status, card_id) = rfid_reader.SelectTagSN()
        if card_status == rfid_reader.OK:
            rfid_card = int.from_bytes(bytes(card_id),"little",False)
            
            if rfid_card == 1497986713:
                display.text("Access",40,40)
                display.text("Accepted",36,50)
                
            elif rfid_card == 540378515:
                display.text("Access",40,40)
                display.text("Denied",40,50)
                
            else:
                print("Detected Card : "+ str(rfid_card))
    display.show()
    utime.sleep(1)
