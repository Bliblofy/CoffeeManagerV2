#!/usr/bin/env python3
"""
DeLonghi Magnifica S RFID Controller - First Iteration
Focus: NFC/RFID reading and basic relay control (No Display)
"""

import RPi.GPIO as GPIO
import time
import spidev
from mfrc522 import MFRC522
import os
import sys
from collections import deque

# Enable import of database manager from ../database
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
from database_manager import CoffeeDatabaseManager

class CoffeeController:
    def __init__(self):
        # GPIO pin configuration based on wiring diagram
        self.RELAY_PINS = {
            'power': 17,      # IN1 - Power button (Pin 11)
            'single': 27,     # IN2 - Single coffee (Pin 13) 
            'double': 22,     # IN3 - Double coffee (Pin 15)
            'steam': 23       # IN4 - Steam/hot water (Pin 16)
        }
        
        # LED indicator configuration
        self.LED_PINS = {
            'red': 5,         # Red LED - System ready/standby (Pin 29)
            'green': 6        # Green LED - Valid card detected/active (Pin 31)
        }
        
        # RC522 NFC configuration
        self.nfc_reader = MFRC522()
        
        # Database and access control configuration
        self.db = CoffeeDatabaseManager()
        # Resolve master token: ENV has priority; fallback to DB setting
        env_master = os.getenv('MASTER_TOKEN_ID')
        db_master = None
        try:
            db_master = self.db.get_setting('master_token_id')
        except Exception:
            db_master = None
        self.master_token_id = env_master if env_master else db_master
        self.master_mode = False
        # Cache scan mode setting
        try:
            self.scan_mode = self.db.get_setting('scan_mode') == '1'
        except Exception:
            self.scan_mode = False
        # Runtime lock to prevent multiple scans while machine is unlocked/active
        self.lock_until_epoch = 0.0
        # Security lockout for brute-force protection
        self.security_lock_until_epoch = 0.0
        # Track timestamps (epoch seconds) of invalid attempts (rolling 60s window)
        self.invalid_attempt_timestamps = deque()
        # Relay deactivation timer (non-blocking)
        self.relay_deactivation_time = 0.0

        self.setup_gpio()
        self.setup_spi()
        
    def setup_gpio(self):
        """Initialize GPIO pins for relay control"""
        # Clean up any existing GPIO state first
        GPIO.cleanup()
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Configure all relay pins as outputs
        for pin in self.RELAY_PINS.values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)   # Relays are active HIGH, start LOW (inactive = open circuit)
            
        # Configure LED pins as outputs
        for pin in self.LED_PINS.values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)   # LEDs start OFF
            
        print("GPIO pins configured for relay control and LED indicators")
        
    def setup_spi(self):
        """Initialize SPI for RC522 NFC reader"""
        try:
            # Enable SPI in raspi-config first if not done
            print("SPI initialized for RC522 NFC reader")
        except Exception as e:
            print(f"SPI setup error: {e}")
            print("Run 'sudo raspi-config' and enable SPI interface")
            
    def _prune_invalid_attempts(self, now_epoch: float):
        """Remove invalid-attempt timestamps older than 60 seconds from the deque."""
        cutoff = now_epoch - 60.0
        while self.invalid_attempt_timestamps and self.invalid_attempt_timestamps[0] < cutoff:
            self.invalid_attempt_timestamps.popleft()

    def _record_invalid_attempt_and_maybe_lock(self, now_epoch: float):
        """Record an invalid attempt; if more than 10 within 60s, engage 5-minute lockout."""
        self._prune_invalid_attempts(now_epoch)
        self.invalid_attempt_timestamps.append(now_epoch)
        # More than 10 invalid attempts in the last 60 seconds triggers lockout
        if len(self.invalid_attempt_timestamps) > 10:
            self.security_lock_until_epoch = now_epoch + 5 * 60.0
            # Clear attempts to avoid immediate re-trigger when lockout ends
            self.invalid_attempt_timestamps.clear()
            # Turn off LEDs during lockout
            try:
                self.set_led_status('off')
            except Exception:
                pass
            print("SECURITY LOCKOUT: Too many invalid IDs. Locked for 5 minutes.")

    def read_nfc_card(self):
        """Read NFC/RFID card and return UID"""
        try:
            # Scan for cards
            (status, tag_type) = self.nfc_reader.MFRC522_Request(self.nfc_reader.PICC_REQIDL)
            
            if status == self.nfc_reader.MI_OK:
                # Get UID
                (status, uid) = self.nfc_reader.MFRC522_Anticoll()
                
                if status == self.nfc_reader.MI_OK:
                    # Convert UID bytes to hex string
                    uid_hex = ''.join([f'{byte:02x}' for byte in uid])
                    return uid_hex
                    
        except Exception as e:
            print(f"NFC read error: {e}")
            
        return None
    
    def is_token_authorized(self, token_id):
        """Check if a token exists in DB and is active and not barred"""
        try:
            # In scan mode, treat all tokens as unauthorized to avoid use; they will be added as pending
            if self.scan_mode:
                return False
            user = self.db.get_user(token_id)
            if not user:
                return False
            if int(user.get('active', 0)) != 1:
                return False
            if int(user.get('barred', 0)) == 1:
                return False
            return True
        except Exception as e:
            print(f"Authorization check error: {e}")
            return False
    
    def enter_master_mode(self):
        """Enable always-on state; only master token can exit."""
        if self.master_mode:
            return
        self.master_mode = True
        self.set_led_status('master')
        # Keep relays on until master mode is toggled off
        try:
            for name, pin in self.RELAY_PINS.items():
                GPIO.output(pin, GPIO.HIGH)
                print(f"  {name} relay forced ON (master mode)")
            print("MASTER MODE ENABLED: Machine is always on. Present master card to exit.")
        except Exception as e:
            print(f"Error enabling master mode: {e}")
    
    def exit_master_mode(self):
        """Disable always-on state and return to normal."""
        if not self.master_mode:
            return
        self.master_mode = False
        try:
            for name, pin in self.RELAY_PINS.items():
                GPIO.output(pin, GPIO.LOW)
                print(f"  {name} relay OFF (exit master mode)")
            self.set_led_status('ready')
            print("MASTER MODE DISABLED: Back to normal operation.")
        except Exception as e:
            print(f"Error disabling master mode: {e}")
        
    def set_led_status(self, status):
        """Set LED status: 'ready' (red), 'active' (green), 'master' (both), or 'off' (both off)"""
        if status == 'ready':
            GPIO.output(self.LED_PINS['red'], GPIO.HIGH)
            GPIO.output(self.LED_PINS['green'], GPIO.LOW)
        elif status == 'active':
            GPIO.output(self.LED_PINS['red'], GPIO.LOW)
            GPIO.output(self.LED_PINS['green'], GPIO.HIGH)
        elif status == 'master':
            GPIO.output(self.LED_PINS['red'], GPIO.HIGH)
            GPIO.output(self.LED_PINS['green'], GPIO.HIGH)
        elif status == 'off':
            GPIO.output(self.LED_PINS['red'], GPIO.LOW)
            GPIO.output(self.LED_PINS['green'], GPIO.LOW)
        
    def activate_all_relays(self, duration=15):
        """Activate all 4 relay channels for specified duration (non-blocking)"""
        print(f"Activating all relays for {duration} seconds...")
        
        try:
            # Activate all relays (set to HIGH - active state)
            for name, pin in self.RELAY_PINS.items():
                GPIO.output(pin, GPIO.HIGH)
                print(f"  {name} relay activated (Pin {pin})")
                
            # Set deactivation timer instead of blocking sleep
            self.relay_deactivation_time = time.time() + duration
            print(f"Relays will auto-deactivate at {self.relay_deactivation_time:.1f}")
            
        except Exception as e:
            print(f"Relay control error: {e}")
            # Emergency shutdown - ensure relays are off
            for pin in self.RELAY_PINS.values():
                GPIO.output(pin, GPIO.LOW)
    
    def check_and_deactivate_relays(self):
        """Check if relays should be deactivated based on timer (non-blocking)"""
        if self.relay_deactivation_time > 0 and time.time() >= self.relay_deactivation_time:
            try:
                # Deactivate all relays (set to LOW - inactive state)
                for name, pin in self.RELAY_PINS.items():
                    GPIO.output(pin, GPIO.LOW)
                    print(f"  {name} relay deactivated (Pin {pin})")
                    
                print("All relays auto-deactivated")
                self.relay_deactivation_time = 0.0  # Reset timer
                # Return LEDs to ready state after deactivation
                self.set_led_status('ready')
                print("\nReady for next card...")
                print("-" * 50)
                
            except Exception as e:
                print(f"Relay deactivation error: {e}")
                # Emergency shutdown - ensure relays are off
                for pin in self.RELAY_PINS.values():
                    GPIO.output(pin, GPIO.LOW)
                self.relay_deactivation_time = 0.0
    
    def get_activation_duration(self):
        """Determine activation duration based on last usage: 30s normal, 2min if >30min since last use
        
        Note: Time accuracy for offline operation:
        - Raspberry Pi uses system clock which may drift without NTP sync
        - For offline operation, consider using RTC module or periodic NTP sync when online
        - Current implementation uses system time which is sufficient for 25-minute threshold
        - Database timestamps are stored in local timezone
        """
        try:
            from datetime import datetime, timedelta
            
            # Get last usage timestamp from database BEFORE logging the new one
            last_usage = self.db.get_last_usage_timestamp()
            now = datetime.now()
            
            if last_usage is None:
                # No previous usage - use extended duration for first boot
                print("No previous usage found - using extended 2-minute activation")
                return 120  # 2 minutes
            
            # Calculate time since last usage
            time_since_last = now - last_usage
            
            # If more than 30 minutes since last use, use extended duration
            if time_since_last > timedelta(minutes=30):
                print(f"Last usage was {time_since_last} ago - using extended 2-minute activation")
                return 120  # 2 minutes
            else:
                print(f"Last usage was {time_since_last} ago - using normal 30-second activation")
                return 30   # 30 seconds
                
        except Exception as e:
            print(f"Error determining activation duration: {e}")
            # Default to normal duration on error
            return 30
                
    def cleanup(self):
        """Clean up GPIO resources"""
        GPIO.cleanup()
        print("GPIO cleanup completed")
        
    def run(self):
        """Main loop for NFC reading and relay control"""
        print("Coffee Controller Started")
        print("Present NFC/RFID card to reader...")
        print("Press Ctrl+C to exit")
        print("-" * 50)
        
        # Set initial LED status to ready (red)
        self.set_led_status('ready')
        
        try:
            while True:
                # Check and deactivate relays if timer expired (non-blocking)
                self.check_and_deactivate_relays()
                
                # refresh scan mode setting periodically
                try:
                    self.scan_mode = self.db.get_setting('scan_mode') == '1'
                except Exception:
                    self.scan_mode = False

                # Read for NFC card
                uid = self.read_nfc_card()
                
                if uid:
                    print(f"\nCard detected! UID: {uid}")
                    
                    # Handle master mode toggle first (master always works, even during lockout)
                    if self.master_token_id and uid == self.master_token_id:
                        # Clear any security lockout on master presentation
                        if time.time() < self.security_lock_until_epoch:
                            self.security_lock_until_epoch = 0.0
                            self.invalid_attempt_timestamps.clear()
                            print("Security lockout cleared by master token.")
                        if self.master_mode:
                            self.exit_master_mode()
                        else:
                            self.enter_master_mode()
                        # Debounce
                        time.sleep(1)
                        continue
                    
                    # If security lockout active and non-master card, ignore
                    if time.time() < self.security_lock_until_epoch:
                        self.set_led_status('off')
                        time.sleep(0.2)
                        continue

                    # If in master mode, ignore all non-master cards
                    if self.master_mode:
                        print("Master mode active: ignoring non-master card")
                        time.sleep(0.5)
                        continue
                    
                    # If machine is currently unlocked/active, ignore further scans until relock
                    now = time.time()
                    if now < self.lock_until_epoch:
                        print("Machine currently active/unlocked; ignoring scan until it locks again.")
                        time.sleep(0.2)
                        continue

                    # If scan mode enabled, create pending user and continue
                    if self.scan_mode:
                        existing = None
                        try:
                            existing = self.db.get_user(uid)
                        except Exception:
                            existing = None
                        if not existing:
                            created = self.db.add_pending_user(uid)
                            print("Pending user created" if created else "Failed to create pending user")
                        else:
                            print("Token already exists; ensure it remains barred until completed.")
                        # Brief LED feedback: stay in ready state
                        time.sleep(0.5)
                        continue

                    # Normal mode: validate token against database
                    if self.is_token_authorized(uid):
                        print("Access granted. Switching to active mode (green LED)...")
                        self.set_led_status('active')
                        
                        # Log usage
                        try:
                            logged = self.db.log_coffee_usage(uid, 'unknown')
                            print("Usage logged" if logged else "Failed to log usage")
                        except Exception as e:
                            print(f"Usage log error: {e}")
                        
                        # Activate relays for dynamic duration based on usage history
                        activation_seconds = self.get_activation_duration()
                        # Set lock to cover activation period plus a short grace period
                        self.lock_until_epoch = time.time() + activation_seconds + 1.0
                        self.activate_all_relays(activation_seconds)
                        
                        # Keep LED green during active window; it will reset to ready when relays auto-deactivate
                        time.sleep(0.1)  # Small debounce to avoid tight loop churn
                    else:
                        print("Access denied: token not found or inactive/barred.")
                        # Record invalid attempt for brute-force protection (normal mode only)
                        self._record_invalid_attempt_and_maybe_lock(time.time())
                        # Brief red flash to indicate denial
                        self.set_led_status('ready')
                        time.sleep(0.8)
                    
                # Small delay between scans
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    try:
        controller = CoffeeController()
        controller.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        GPIO.cleanup()

if __name__ == "__main__":
    main()
