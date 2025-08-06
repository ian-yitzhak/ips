import requests
import base64
import json
import time
import threading
from picamera2 import Picamera2
from datetime import datetime
import os
import RPi.GPIO as GPIO

# Set custom media directory
MEDIA_DIR = "/home/rpi5/CamTry/Photos_Vids"
os.makedirs(MEDIA_DIR, exist_ok=True)

def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

class SimpleParkingCamera:
    def __init__(self, server_url):
        self.server_url = server_url
        self.camera = None
        self.pwm = None
        self.setup_gate_servo()
    
    def setup_camera(self):
        """Initialize camera"""
        try:
            self.camera = Picamera2()
            # Configure camera
            config = self.camera.create_still_configuration(
                main={"size": (1920, 1080)},
                lores={"size": (640, 480)},
                display="lores"
            )
            self.camera.configure(config)
            self.camera.start()
            time.sleep(2)  # Let camera warm up
            print(f"[{timestamp()}] Camera initialized successfully")
        except Exception as e:
            print(f"[{timestamp()}] Camera setup failed: {e}")
    
    def setup_gate_servo(self):
        """Initialize servo motor for gate control"""
        try:
            self.Servo_Pin = 6
            self.PWM_FREQUENCY = 50
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.Servo_Pin, GPIO.OUT)
            self.pwm = GPIO.PWM(self.Servo_Pin, self.PWM_FREQUENCY)
            self.pwm.start(0)
            print(f"[{timestamp()}] Servo motor initialized")
        except Exception as e:
            print(f"[{timestamp()}] Servo setup failed: {e}")
    
    def set_gate_angle(self, angle):
        """Set gate angle (0 = closed, 90 = open)"""
        if self.pwm:
            duty_cycle = 2 + (angle/18)
            self.pwm.ChangeDutyCycle(duty_cycle)
            time.sleep(0.1)
            self.pwm.ChangeDutyCycle(0)
    
    def operate_gate(self):
        """Open gate for 10 seconds then close it"""
        try:
            self.set_gate_angle(90)
            print(f"[{timestamp()}] Gate Opened")
            time.sleep(10)  # Keep gate open for 10 seconds
            self.set_gate_angle(0)
            print(f"[{timestamp()}] Gate Closed")
        except Exception as e:
            print(f"[{timestamp()}] Error operating gate: {e}")
    
    def capture_image(self):
        """Capture image from camera"""
        try:
            ts = timestamp()
            filename = f"{MEDIA_DIR}/vehicle_cam0_{ts}.jpg"
            
            # Take picture
            self.camera.capture_file(filename)
            print(f"[{timestamp()}] Image captured: vehicle_cam0_{ts}.jpg")
            
            return filename
        except Exception as e:
            print(f"[{timestamp()}] Failed to capture image: {e}")
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
                'camera_name': 'cam_0',
                'timestamp': datetime.now().isoformat()
            }
            
            # Send to server
            url = f"{self.server_url}/api/capture-image/"
            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                print(f"[{timestamp()}] ✅ Image sent successfully! Entry ID: {result['entry_id']}")
                
                # Delete local file after successful upload
                os.remove(image_path)
                
                # Open and close the gate after successful image processing
                self.operate_gate()
                return True
            else:
                print(f"[{timestamp()}] ❌ Failed to send image: {response.text}")
                return False
                
        except Exception as e:
            print(f"[{timestamp()}] Error sending image: {e}")
            return False
    
    def cleanup(self):
        """Clean up resources"""
        if self.camera:
            self.camera.stop()
        if self.pwm:
            self.pwm.stop()
        GPIO.cleanup()
        print(f"[{timestamp()}] Camera and servo stopped")

def run_camera(camera_system, interval=30, duration=300):
    """Run camera monitoring for specified duration"""
    print(f"[{timestamp()}] Starting Camera 0 monitoring for {duration}s")
    
    # Setup camera
    camera_system.setup_camera()
    
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            # Capture image
            image_path = camera_system.capture_image()
            
            if image_path:
                # Send to server
                success = camera_system.send_image_to_server(image_path)
                
                if success:
                    print(f"[{timestamp()}] Image processed successfully")
                else:
                    print(f"[{timestamp()}] Failed to process image")
            
            # Wait before next capture
            time.sleep(interval)
            
    except Exception as e:
        print(f"[{timestamp()}] Error in camera monitoring: {e}")
    finally:
        camera_system.cleanup()

def main():
    print(f"[{timestamp()}] Parking Camera Script started.")
    
    server_url = "http://192.168.100.3:8000"
    camera_system = SimpleParkingCamera(server_url)
    
    print(f"[{timestamp()}] Starting Camera 0 for 300 seconds...")
    
    # Create and start thread for camera 0
    cam_1 = threading.Thread(target=run_camera, args=(camera_system, 30, 300))
    cam_1.start()
    cam_1.join()
    
    print(f"[{timestamp()}] Camera monitoring complete.")

if __name__ == "__main__":
    main()
