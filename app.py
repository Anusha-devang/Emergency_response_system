from flask import Flask, jsonify, send_from_directory, request
import json
import math
from datetime import datetime

app = Flask(__name__)

class RealTimeProcessor:
    def __init__(self):
        self.vehicle_locations = {}
        self.phone_to_location = {}
        self.load_vehicles()
        # Sample phone number to location mapping
        self.phone_locations = {
            "9876543210": {"lat": 13.3409, "lng": 77.1025, "address": "Tumkur City Center"},
            "9876543211": {"lat": 13.3415, "lng": 77.1030, "address": "Tumkur Bus Stand"},
            "9876543212": {"lat": 13.3420, "lng": 77.1035, "address": "Tumkur Railway Station"},
            "9876543213": {"lat": 13.3425, "lng": 77.1040, "address": "Tumkur Medical College"},
            "9876543214": {"lat": 13.3430, "lng": 77.1045, "address": "Tumkur Police Station"}
        }
        print("RealTimeProcessor initialized with phone locations")
        
    def load_vehicles(self):
        try:
            with open('data/vehicles.json', 'r') as f:
                data = json.load(f)
                self.vehicles = data.get('vehicles', [])
                # Add ETA field to each vehicle
                for vehicle in self.vehicles:
                    vehicle['eta'] = "N/A"
                    # Set all vehicles as available initially
                    vehicle['available'] = True
                    vehicle['status'] = 'AVAILABLE'
        except Exception as e:
            print(f"Error loading vehicles: {e}")
            self.vehicles = []

    def update_vehicle_location(self, vehicle_id, location):
        self.vehicle_locations[vehicle_id] = location

    def update_phone_location(self, phone, location):
        self.phone_to_location[phone] = location

    def get_vehicle_location(self, vehicle_id):
        return self.vehicle_locations.get(vehicle_id)

    def get_phone_location(self, phone):
        return self.phone_to_location.get(phone)

    def get_location_from_phone(self, phone_number):
        print(f"Getting location for phone number: {phone_number}")
        # Get location from mapping
        location = self.phone_locations.get(phone_number)
        if location:
            print(f"Found location for {phone_number}: {location}")
            return {
                'location': {'lat': location['lat'], 'lng': location['lng']},
                'address': location['address']
            }
        print(f"No location found for phone number: {phone_number}")
        return None

    def calculate_eta(self, vehicle_location, emergency_location):
        if not vehicle_location or not emergency_location:
            return 0

        # Convert location keys to match the format
        vehicle_lat = vehicle_location.get('latitude', vehicle_location.get('lat'))
        vehicle_lng = vehicle_location.get('longitude', vehicle_location.get('lng'))
        emergency_lat = emergency_location.get('latitude', emergency_location.get('lat'))
        emergency_lng = emergency_location.get('longitude', emergency_location.get('lng'))

        if not all([vehicle_lat, vehicle_lng, emergency_lat, emergency_lng]):
            return 0

        # Calculate distance using Haversine formula
        R = 6371  # Earth's radius in kilometers

        lat1, lon1 = math.radians(float(vehicle_lat)), math.radians(float(vehicle_lng))
        lat2, lon2 = math.radians(float(emergency_lat)), math.radians(float(emergency_lng))

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c

        # Calculate time based on vehicle type and distance
        speed = 60  # Default speed in km/h
        time_hours = distance / speed
        eta_minutes = round(time_hours * 60, 1)  # Convert to minutes and round to 1 decimal

        # Ensure minimum ETA of 1 minute for any non-zero distance
        if eta_minutes < 1 and distance > 0:
            eta_minutes = 1

        # Store the distance in the vehicle object for display
        vehicle = next((v for v in self.vehicles if v['location']['latitude'] == vehicle_lat and v['location']['longitude'] == vehicle_lng), None)
        if vehicle:
            vehicle['distance'] = round(distance, 1)

        return eta_minutes

processor = RealTimeProcessor()

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    # Get service type from query parameter
    service_type = request.args.get('type', '').upper()
    
    if service_type:
        # Filter vehicles by type and availability
        filtered_vehicles = [
            vehicle for vehicle in processor.vehicles 
            if vehicle['type'] == service_type and vehicle['available']
        ]
        return jsonify(filtered_vehicles)
    
    return jsonify(processor.vehicles)

@app.route('/api/location/<phone_number>')
def get_location(phone_number):
    location_data = processor.get_location_from_phone(phone_number)
    if location_data:
        # Calculate ETAs for all vehicles
        for vehicle in processor.vehicles:
            vehicle_location = {
                'latitude': vehicle['location']['latitude'],
                'longitude': vehicle['location']['longitude']
            }
            eta = processor.calculate_eta(vehicle_location, location_data['location'])
            vehicle['eta'] = f"{eta} mins" if eta > 0 else "N/A"
        return jsonify(location_data)
    return jsonify({'error': 'Location not found'}), 404

@app.route('/api/calculate-etas', methods=['POST'])
def calculate_etas():
    try:
        data = request.get_json()
        print("Received ETA calculation request:", data)
        
        emergency_location = data.get('location')
        vehicle_ids = data.get('vehicleIds', [])
        
        if not emergency_location or not vehicle_ids:
            print("Missing location or vehicle IDs")
            return jsonify({'error': 'Missing location or vehicle IDs'}), 400
        
        etas = []
        for vehicle in processor.vehicles:
            if vehicle['id'] in vehicle_ids:
                print(f"Calculating ETA for vehicle {vehicle['id']}")
                vehicle_location = {
                    'latitude': vehicle['location']['latitude'],
                    'longitude': vehicle['location']['longitude']
                }
                eta = processor.calculate_eta(vehicle_location, emergency_location)
                vehicle['eta'] = f"{eta} mins" if eta > 0 else "N/A"
                etas.append({
                    'vehicleId': vehicle['id'],
                    'vehicleName': vehicle['name'],
                    'vehicleType': vehicle['type'],
                    'etaMinutes': eta,
                    'status': vehicle['status'],
                    'available': vehicle['available'],
                    'services': vehicle.get('services', [])
                })
        
        print("Calculated ETAs:", etas)
        return jsonify({'etas': etas})
    except Exception as e:
        print(f"Error in calculate_etas: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/location', methods=['POST'])
def update_location():
    data = request.get_json()
    phone = data.get('phone')
    location = data.get('location')
    
    if phone and location:
        processor.update_phone_location(phone, location)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

@app.route('/api/dispatch', methods=['POST'])
def dispatch_vehicle():
    request_data = request.get_json()
    vehicle_id = request_data.get('vehicle_id')
    phone = request_data.get('phone')
    
    if not vehicle_id or not phone:
        return jsonify({'status': 'error', 'message': 'Missing vehicle_id or phone'}), 400

    emergency_location = processor.get_phone_location(phone)
    if not emergency_location:
        return jsonify({'status': 'error', 'message': 'Emergency location not found'}), 404

    vehicle = next((v for v in processor.vehicles if v['id'] == vehicle_id), None)
    if not vehicle:
        return jsonify({'status': 'error', 'message': 'Vehicle not found'}), 404

    vehicle_location = {
        'latitude': vehicle['location']['latitude'],
        'longitude': vehicle['location']['longitude']
    }

    eta = processor.calculate_eta(vehicle_location, emergency_location)
    
    # Update vehicle status
    vehicle['available'] = False
    vehicle['status'] = 'EN_ROUTE'
    vehicle['eta'] = f"{eta} mins"

    return jsonify({
        'status': 'success',
        'eta': eta,
        'vehicle': vehicle
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)