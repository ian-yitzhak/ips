#!/usr/bin/env python3
"""
LCD Parking Slot Counter Display
File: lcd_parking_counter.py

Simple LCD display system that shows current parking slot availability
by syncing with Django database every 30 seconds.
"""

import time
import requests
import json
from datetime import datetime
from smbus2 import SMBus
import threading

# --- CONFIGURATION ---
DJANGO_SERVER_URL = "http://192.168.100.3:8000"  # Update with your Django server IP
SYNC_INTERVAL = 30  # Sync with Django every 30 seconds
DEFAULT_TOTAL_SLOTS = 5  # Fallback if Django is unreachable

# --- LCD SETUP using I2C address 0x3f ---
I2C_ADDR = 0x3f
LCD_WIDTH = 16
LCD_CHR = 1
LCD_CMD = 0
LCD_LINE_1 = 0x80
LCD_LINE_2 = 0xC0
LCD_BACKLIGHT = 0x08
ENABLE = 0b00000100

try:
    bus = SMBus(1)  # I2C bus 1
    LCD_AVAILABLE = True
except Exception as e:
    print(f"Warning: LCD not available - {e}")
    LCD_AVAILABLE = False

class ParkingSlotDisplay:
    def __init__(self):
        self.total_slots = DEFAULT_TOTAL_SLOTS
        self.occupied_slots = 0
        self.last_sync_time = 0
        self.lcd_initialized = False
        
        if LCD_AVAILABLE:
            self.init_lcd()
        
        # Initial sync
        self.sync_with_django()
    
    @property
    def available_slots(self):
        return self.total_slots - self.occupied_slots
    
    @property
    def is_full(self):
        return self.available_slots == 0
    
    def timestamp(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def lcd_byte(self, bits, mode):
        """Send byte to LCD"""
        if not LCD_AVAILABLE:
            return
        try:
            high = mode | (bits & 0xF0) | LCD_BACKLIGHT
            low = mode | ((bits << 4) & 0xF0) | LCD_BACKLIGHT
            bus.write_byte(I2C_ADDR, high)
            self.lcd_toggle_enable(high)
            bus.write_byte(I2C_ADDR, low)
            self.lcd_toggle_enable(low)
        except Exception as e:
            print(f"LCD byte error: {e}")
    
    def lcd_toggle_enable(self, bits):
        """Toggle enable pin"""
        time.sleep(0.0005)
        bus.write_byte(I2C_ADDR, (bits | ENABLE))
        time.sleep(0.0005)
        bus.write_byte(I2C_ADDR, (bits & ~ENABLE))
        time.sleep(0.0005)
    
    def init_lcd(self):
        """Initialize LCD display"""
        if not LCD_AVAILABLE:
            return
        try:
            self.lcd_byte(0x33, LCD_CMD)
            self.lcd_byte(0x32, LCD_CMD)
            self.lcd_byte(0x06, LCD_CMD)
            self.lcd_byte(0x0C, LCD_CMD)
            self.lcd_byte(0x28, LCD_CMD)
            self.lcd_byte(0x01, LCD_CMD)
            time.sleep(0.05)
            self.lcd_initialized = True
            
            # Show startup message
            self.lcd_message(" Parking Counter", LCD_LINE_1)
            self.lcd_message("  Initializing..", LCD_LINE_2)
            time.sleep(2)
            print(f"[{self.timestamp()}] LCD initialized successfully")
            
        except Exception as e:
            print(f"[{self.timestamp()}] LCD initialization failed: {e}")
            self.lcd_initialized = False
    
    def lcd_message(self, message, line):
        """Display message on LCD"""
        if not LCD_AVAILABLE or not self.lcd_initialized:
            return
        try:
            self.lcd_byte(line, LCD_CMD)
            for char in message.ljust(LCD_WIDTH):
                self.lcd_byte(ord(char), LCD_CHR)
        except Exception as e:
            print(f"LCD message error: {e}")
    
    def clear_lcd(self):
        """Clear LCD screen"""
        if LCD_AVAILABLE and self.lcd_initialized:
            self.lcd_byte(0x01, LCD_CMD)
            time.sleep(0.05)
    
    def update_display(self):
        """Update LCD with current parking status"""
        if not LCD_AVAILABLE:
            # Console output if no LCD
            print(f"[{self.timestamp()}] Parking Status: {self.available_slots}/{self.total_slots} available")
            return
        
        self.clear_lcd()
        
        if self.available_slots > 0:
            # Show available slots
            self.lcd_message("  SPACES LEFT", LCD_LINE_1)
            self.lcd_message(f"   {self.available_slots:02d}/{self.total_slots:02d} FREE", LCD_LINE_2)
        else:
            # Show parking full
            self.lcd_message("   PARKING", LCD_LINE_1)
            self.lcd_message("    FULL!", LCD_LINE_2)
        
        print(f"[{self.timestamp()}] LCD Updated: {self.available_slots}/{self.total_slots} available")
    
    def sync_with_django(self):
        """Sync parking slots count with Django database"""
        try:
            response = requests.get(f"{DJANGO_SERVER_URL}/api/parking-slots/", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    slot_data = data['data']
                    old_occupied = self.occupied_slots
                    old_total = self.total_slots
                    
                    self.total_slots = slot_data['total_slots']
                    self.occupied_slots = slot_data['occupied_slots']
                    self.last_sync_time = time.time()
                    
                    # Only update display if something changed
                    if old_occupied != self.occupied_slots or old_total != self.total_slots:
                        self.update_display()
                    
                    print(f"[{self.timestamp()}] ✅ SYNC: {self.occupied_slots}/{self.total_slots} occupied")
                    return True
            else:
                print(f"[{self.timestamp()}] ⚠️ Django sync failed: HTTP {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"[{self.timestamp()}] 🔌 Django server unreachable")
        except requests.exceptions.Timeout:
            print(f"[{self.timestamp()}] ⏰ Django server timeout")
        except Exception as e:
            print(f"[{self.timestamp()}] ❌ Django sync error: {e}")
        
        return False
    
    def show_sync_message(self):
        """Show syncing message on LCD"""
        if LCD_AVAILABLE and self.lcd_initialized:
            self.clear_lcd()
            self.lcd_message("   SYNCING...", LCD_LINE_1)
            self.lcd_message("", LCD_LINE_2)
            time.sleep(1)
    
    def show_error_message(self):
        """Show error message on LCD"""
        if LCD_AVAILABLE and self.lcd_initialized:
            self.clear_lcd()
            self.lcd_message("  CONNECTION", LCD_LINE_1)
            self.lcd_message("    ERROR!", LCD_LINE_2)
            time.sleep(2)
    
    def periodic_sync(self):
        """Periodically sync with Django server"""
        consecutive_failures = 0
        
        while True:
            try:
                time.sleep(SYNC_INTERVAL)
                
                print(f"[{self.timestamp()}] 🔄 Starting periodic sync...")
                self.show_sync_message()
                
                if self.sync_with_django():
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        print(f"[{self.timestamp()}] ⚠️ Multiple sync failures - showing error")
                        self.show_error_message()
                        self.update_display()  # Restore display
                
            except Exception as e:
                print(f"[{self.timestamp()}] ❌ Periodic sync error: {e}")
                consecutive_failures += 1
    
    def run(self):
        """Main run method"""
        print(f"[{self.timestamp()}] 🚀 PARKING SLOT COUNTER STARTING...")
        print(f"[{self.timestamp()}] 🌐 Django Server: {DJANGO_SERVER_URL}")
        print(f"[{self.timestamp()}] 📺 LCD Status: {'Connected' if LCD_AVAILABLE else 'Disabled'}")
        print(f"[{self.timestamp()}] 🔄 Sync Interval: {SYNC_INTERVAL} seconds")
        print("=" * 50)
        
        # Initial display update
        self.update_display()
        
        # Start periodic sync thread
        sync_thread = threading.Thread(target=self.periodic_sync, daemon=True)
        sync_thread.start()
        
        print(f"[{self.timestamp()}] ✅ SYSTEM READY - Monitoring parking slots...")
        
        # Keep script running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[{self.timestamp()}] 🛑 SHUTDOWN: Cleaning up...")
            if LCD_AVAILABLE and self.lcd_initialized:
                self.clear_lcd()
                self.lcd_message("   SYSTEM", LCD_LINE_1)
                self.lcd_message("  SHUTDOWN", LCD_LINE_2)
                time.sleep(2)
                self.clear_lcd()
            print(f"[{self.timestamp()}] ✅ Program exited cleanly.")

def main():
    """Main function"""
    display = ParkingSlotDisplay()
    display.run()

if __name__ == "__main__":
    main()
