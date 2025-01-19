from mfrc522 import MFRC522
import utime
 
rfid_reader = MFRC522(spi_id=0,sck=2,miso=4,mosi=7,cs=5,rst=18)
 
print("Waiting for the card swipe...")
 
 
while True:
    rfid_reader.init()
    (card_status, tag_type) = rfid_reader.request(rfid_reader.REQIDL)
    if card_status == rfid_reader.OK:
        (card_status, card_id) = rfid_reader.SelectTagSN()
        if card_status == rfid_reader.OK:
            rfid_card = int.from_bytes(bytes(card_id),"little",False)
            print("Detected Card : "+ str(rfid_card))
utime.sleep_ms(500) 
