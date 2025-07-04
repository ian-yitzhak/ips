# raspberry_pi_camera.py
import requests
import base64
import json
import time
from picamera2 import Picamera2
from datetime import datetime
import os

class SimpleParkingCamera:
    def __init__(self, server_url):
        self.server_url = server_url
        self.camera = Picamera2()
        self.setup_camera()
    
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
            print("Camera stopped")

if __name__ == "__main__":
    server_url = "http://192.168.1.100:8000"  # Replace with your server IP
    camera = SimpleParkingCamera(server_url)
    camera.start_monitoring(interval=30)
