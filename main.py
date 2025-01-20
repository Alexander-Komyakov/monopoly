from micropython import const
import framebuf
from machine import Pin, SoftI2C, SPI
import time
import utime
from mfrc522 import MFRC522
from keypad import Keypad
import _thread

# register definitions
SET_CONTRAST        = const(0x81)
SET_ENTIRE_ON       = const(0xa4)
SET_NORM_INV        = const(0xa6)
SET_DISP            = const(0xae)
SET_MEM_ADDR        = const(0x20)
SET_COL_ADDR        = const(0x21)
SET_PAGE_ADDR       = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP       = const(0xa0)
SET_MUX_RATIO       = const(0xa8)
SET_COM_OUT_DIR     = const(0xc0)
SET_DISP_OFFSET     = const(0xd3)
SET_COM_PIN_CFG     = const(0xda)
SET_DISP_CLK_DIV    = const(0xd5)
SET_PRECHARGE       = const(0xd9)
SET_VCOM_DESEL      = const(0xdb)
SET_CHARGE_PUMP     = const(0x8d)


class SSD1306:
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        fb = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.framebuf = fb
        # Provide methods for accessing FrameBuffer graphics primitives. This is a
        # workround because inheritance from a native class is currently unsupported.
        # http://docs.micropython.org/en/latest/pyboard/library/framebuf.html
        self.fill = fb.fill
        self.pixel = fb.pixel
        self.hline = fb.hline
        self.vline = fb.vline
        self.line = fb.line
        self.rect = fb.rect
        self.fill_rect = fb.fill_rect
        self.text = fb.text
        self.scroll = fb.scroll
        self.blit = fb.blit
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP | 0x00, # off
            # address setting
            SET_MEM_ADDR, 0x00, # horizontal
            # resolution and layout
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01, # column addr 127 mapped to SEG0
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08, # scan from COM[N] to COM0
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, 0x02 if self.height == 32 else 0x12,
            # timing and driving scheme
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0x22 if self.external_vcc else 0xf1,
            SET_VCOM_DESEL, 0x30, # 0.83*Vcc
            # display
            SET_CONTRAST, 0xff, # maximum
            SET_ENTIRE_ON, # output follows RAM contents
            SET_NORM_INV, # not inverted
            # charge pump
            SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01): # on
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        x0 = 0
        x1 = self.width - 1
        if self.width == 64:
            # displays with width of 64 pixels are shifted by 32
            x0 += 32
            x1 += 32
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)
        
    def write_text(self, text, x, y, size):
        ''' Method to write Text on OLED/LCD Displays with a variable font size

            Args:
                text: the string of chars to be displayed
                x: x co-ordinate of starting position
                y: y co-ordinate of starting position
                size: font size of text
                color: color of text to be displayed
        '''
        background = 0
        # clear screen
        #self.fill(background)
        info = []
        # Creating reference characters to read their values
        self.text(text, x, y)
        for i in range(x, x + (8 * len(text))):
            for j in range(y, y + 8):
                # Fetching and saving details of pixels, such as
                # x co-ordinate, y co-ordinate, and color of the pixel
                px_color = self.pixel(i, j)                
                info.append((i, j, px_color))
        # Clearing the reference characters from the screen
        self.text(text, x, y, background)        
        # Writing the custom-sized font characters on screen
        for px_info in info:
            self.fill_rect(size * px_info[0] - (size - 1) * x,
                           size * px_info[1] - (size - 1) * y,
                           size, size, px_info[2])        


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3c, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80 # Co=1, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        self.temp[0] = self.addr << 1
        self.temp[1] = 0x40 # Co=0, D/C#=1
        self.i2c.start()
        self.i2c.write(self.temp)
        self.i2c.write(buf)
        self.i2c.stop()


class SSD1306_SPI(SSD1306):
    def __init__(self, width, height, spi, dc, res, cs, external_vcc=False):
        self.rate = 10 * 1024 * 1024
        dc.init(dc.OUT, value=0)
        res.init(res.OUT, value=0)
        cs.init(cs.OUT, value=1)
        self.spi = spi
        self.dc = dc
        self.res = res
        self.cs = cs
        import time
        self.res(1)
        time.sleep_ms(1)
        self.res(0)
        time.sleep_ms(10)
        self.res(1)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(buf)
        self.cs(1)
        
        
class Game:
    def __init__(self):
        self.players = [99000, 1500, 1500, 1500, 1500, 1500, 1500, 1500]
        self.players_rfid = {"3308833859": 0, "619441987": 1, "34": 2, "43": 3, "53": 4, "35": 5, "22": 6, "12": 7}
        
        self.state_game = "" # "" "plus1" "plus2" "minus1" "minus2" "trade1" "trade2" "trade3" "trade4"
        self.number = ""
        
        # Oled
        self.i2c = SoftI2C(sda=Pin(0), scl=Pin(1))
        self.oled_width = 128
        self.oled_height = 64
        self.oled = SSD1306_I2C(self.oled_width, self.oled_height, self.i2c)

        # RFID
        self.rfid_reader = MFRC522(spi_id=0,sck=6,miso=4,mosi=7,cs=5,rst=22)

        # Keypad
        # Define GPIO pins for rows
        self.row_pins = [Pin(13),Pin(12),Pin(11),Pin(10)]
        # Define GPIO pins for columns
        self.column_pins = [Pin(9),Pin(8),Pin(3),Pin(2)]
        # Define keypad layout
        self.keys = [
            ['1', '2', '3', 'A'],
            ['4', '5', '6', 'B'],
            ['7', '8', '9', 'C'],
            ['*', '0', '#', 'D']]

        self.keypad = Keypad(self.row_pins, self.column_pins, self.keys)
        
        self.rfid_reader.init()

        
    def keypad_thread(self):
        state = False
        while True:
            key_pressed = self.keypad.read_keypad()
            if (key_pressed != None) and (state == False):
                if key_pressed == "D": #trade
                    if self.state_game == "trade1" and len(self.number) > 1:
                        self.number = self.number[:-1]
                        self.show_trade(self.number)
                    if self.state_game == "minus1" and len(self.number) > 1:
                        self.number = self.number[:-1]
                        self.show_minus(self.number)
                    if self.state_game == "plus1" and len(self.number) > 1:
                        self.number = self.number[:-1]
                        self.show_plus(self.number)
                if key_pressed == "B": #trade
                    self.number = ""
                    self.state_game = "trade1"
                    self.show_trade(self.number)
                if key_pressed == "C": #break
                    self.show_score_all()
                    self.state_game = ""
                    self.number = ""
                if key_pressed == "#": #minus
                    self.number = ""
                    self.state_game = "minus1"
                    self.show_minus(self.number)
                if key_pressed == "*": #plus
                    self.number = ""
                    self.state_game = "plus1"
                    self.show_plus(self.number)
                if key_pressed in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
                    if self.state_game == "plus1" and len(self.number) < 5:
                        self.number = self.number + key_pressed
                        self.show_plus(self.number)
                    if self.state_game == "minus1" and len(self.number) < 5:
                        self.number = self.number + key_pressed
                        self.show_minus(self.number)
                    if self.state_game == "trade1" and len(self.number) < 5:
                        self.number = self.number + key_pressed
                        self.show_trade(self.number)
                if key_pressed == "A": #approve
                    if self.state_game == "plus1":
                        if self.number != "":
                            self.state_game = "plus2"
                            self.number = self.number + "A"
                            self.show_plus(self.number)
                        else:
                            self.show_score_all()
                            self.state_game = ""
                            self.number = ""
                    if self.state_game == "minus1":
                        if self.number != "":
                            self.state_game = "minus2"
                            self.number = self.number + "A"
                            self.show_minus(self.number)
                        else:
                            self.show_score_all()
                            self.state_game = ""
                            self.number = ""
                    if self.state_game == "trade1":
                        if self.number != "":
                            self.state_game = "trade2"
                            self.number = self.number + "A"
                            self.show_trade(self.number)
                        else:
                            self.show_score_all()
                            self.state_game = ""
                            self.number = ""
                    
                state = True
            elif key_pressed == None:
                state = False

    def run_game(self):
        _thread.start_new_thread(self.keypad_thread, ())
        self.show_score_all()
        while True:
            (card_status, tag_type) = self.rfid_reader.request(self.rfid_reader.REQIDL)
            if card_status == self.rfid_reader.OK:
                (card_status, card_id) = self.rfid_reader.SelectTagSN()
                if card_status == self.rfid_reader.OK:
                    rfid_card = str(int.from_bytes(bytes(card_id),"little",False))
                    if rfid_card in self.players_rfid.keys():
                        player_id = self.players_rfid[rfid_card]
                        if self.state_game == "plus2":
                            self.players[player_id] = self.players[player_id] + int(self.number[:-1])
                            self.state_game = ""
                            self.number = ""
                            self.show_score_one(player_id)
                        elif self.state_game == "minus2":
                            if (self.players[player_id] - int(self.number[:-1])) >= 0:
                                self.players[player_id] = self.players[player_id] - int(self.number[:-1])
                                self.state_game = ""
                                self.number = ""
                                self.show_score_one(player_id)
                            else:
                                self.show_not_enough(self.players[player_id] - int(self.number[:-1]))
                                self.state_game = ""
                                self.number = ""
                        elif self.state_game == "trade2":
                            if (self.players[player_id] - int(self.number[:-1])) >= 0:
                                self.save_player_id_trade = player_id
                                self.show_score_one_number((self.players[player_id] - int(self.number[:-1])))
                                self.state_game = "trade3"
                            else:
                                self.show_not_enough(self.players[player_id] - int(self.number[:-1]))
                                self.state_game = ""
                                self.number = ""
                        elif self.state_game == "trade3":
                            self.players[self.save_player_id_trade] = self.players[self.save_player_id_trade] - int(self.number[:-1])
                            self.players[player_id] = self.players[player_id] + int(self.number[:-1])
                            self.state_game = ""
                            self.number = ""
                            self.show_score_one(player_id)
                            self.save_player_id_trade = -1
                        else:
                            self.show_score_one(player_id)

    
    def show_score_all(self):
        self.oled.fill(0)
        for i in range(0, 8):
            self.oled.write_text(f"{i+1}: {self.players[i]}", 0, i*8, 1)
        self.oled.show()
    
    def show_score_one(self, player):
        self.oled.fill(0)
        if self.players[player] > 99999:
            self.oled.write_text(f"{self.players[player]}", 0, 24, 2)
        else:    
            self.oled.write_text(f"{self.players[player]}", 0, 24, 3)
        self.oled.show()
        
    def show_score_one_number(self, number):
        self.oled.fill(0)
        if number > 99999:
            self.oled.write_text(str(number), 0, 24, 2)
        else:    
            self.oled.write_text(str(number), 0, 24, 3)
        self.oled.show()
    
    def show_trade(self, number):
        self.oled.fill(0)
        self.oled.write_text(f"T{number}", 0, 26, 2)
        self.oled.show()
    
    def show_plus(self, number):
        self.oled.fill(0)
        self.oled.write_text(f"+{number}", 0, 26, 2)
        self.oled.show()
    
    def show_minus(self, number):
        self.oled.fill(0)
        self.oled.write_text(f"-{number}", 0, 26, 2)
        self.oled.show()
    
    def show_not_enough(self, number):
        self.oled.fill(0)
        if int(self.number[:-1]) > 9999:
            self.oled.write_text(f"NO {number}", 0, 26, 1)
        else:
            self.oled.write_text(f"NO {number}", 0, 26, 2)
        self.oled.show()

game = Game()
game.run_game()
