import requests
import base64
import json
import time
from picamera2 import Picamera2
from datetime import datetime
import os
import RPi.GPIO as GPIO

class SimpleParkingCamera:
    def __init__(self, server_url):
        self.server_url = server_url
        self.camera = Picamera2()
        self.setup_camera()
        self.setup_gate_servo()
    
    def setup_camera(self):
        """Initialize camera"""
        try:
            # Configure camera
            config = self.camera.create_still_configuration(
                main={"size": (1920, 1080)},
                lores={"size": (640, 480)},
                display="lores"
            )
            self.camera.configure(config)
            self.camera.start()
            time.sleep(2)  # Let camera warm up
            print("Camera initialized successfully")
        except Exception as e:
            print(f"Camera setup failed: {e}")
    
    def setup_gate_servo(self):
        """Initialize servo motor for gate control"""
        self.Servo_Pin = 6
        self.PWM_FREQUENCY = 50
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.Servo_Pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.Servo_Pin, self.PWM_FREQUENCY)
        self.pwm.start(0)
        print("Servo motor initialized")
    
    def set_gate_angle(self, angle):
        """Set gate angle (0 = closed, 90 = open)"""
        duty_cycle = 2 + (angle/18)
        self.pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(0.1)
        self.pwm.ChangeDutyCycle(0)
    
    def operate_gate(self):
        """Open gate for 10 seconds then close it"""
        try:
            self.set_gate_angle(90)
            print("Gate Opened")
            time.sleep(10)  # Keep gate open for 10 seconds
            self.set_gate_angle(0)
            print("Gate Closed")
        except Exception as e:
            print(f"Error operating gate: {e}")
    
    def capture_image(self):
        """Capture image from camera"""
        try:
            # Capture image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"vehicle_{timestamp}.jpg"
            
            # Take picture
            self.camera.capture_file(filename)
            print(f"Image captured: {filename}")
            
            return filename
        except Exception as e:
            print(f"Failed to capture image: {e}")
            return None
    
    def send_image_to_server(self, image_path, color="unknown"):
        """Send image to Django server"""
        try:
            # Read and encode image
            with open(image_path, 'rb') as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Prepare data
            data = {
                'image': image_data,
                'color': color,
                'timestamp': datetime.now().isoformat()
            }
            
            # Send to server
            url = f"{self.server_url}/api/capture-image/"
            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Image sent successfully! Entry ID: {result['entry_id']}")
                
                # Delete local file after successful upload
                os.remove(image_path)
                
                # Open and close the gate after successful image processing
                self.operate_gate()
                return True
            else:
                print(f"✗ Failed to send image: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending image: {e}")
            return False
    
    def start_monitoring(self, interval=30):
        """Start continuous monitoring"""
        print("Starting parking monitoring...")
        print(f"Capturing images every {interval} seconds")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                # Capture image
                image_path = self.capture_image()
                
                if image_path:
                    # Send to server
                    success = self.send_image_to_server(image_path)
                    
                    if success:
                        print("Image processed successfully")
                    else:
                        print("Failed to process image")
                
                # Wait before next capture
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nStopping monitoring...")
            self.camera.stop()
            self.pwm.stop()
            GPIO.cleanup()
            print("Camera and servo stopped")

if __name__ == "__main__":
    server_url = "http://192.168.100.3:8000"  # Updated with your IP address
    camera = SimpleParkingCamera(server_url)
    camera.start_monitoring(interval=30)
