import sys
import math
import json
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import tkinter as tk
from collections import deque
from TraconSelection import TraconSelectionDialog
from geojsonLoader import GeoJsonLoader
from DataFetcher import DataFetcher
import os


DCB_COLOR = "#3a3f40"
BUTTON_STRIP_COLOR = "#5c6769"
BUTTON_WIDTH = 15
BUTTON_HEIGHT = 2
DCB_HEIGHT = 80
FONT = ("Roboto", 10)
SCREEN_WIDTH = 800


class TRACONDisplay(QMainWindow):
    def __init__(self, tracon_config):
        super().__init__()

        self.setCursor(Qt.CrossCursor)

       # Load the font
        font_id = QFontDatabase.addApplicationFont("Resources/fonts/Roboto_Mono/RobotoMono-Bold.ttf")
        if font_id == -1:
            print("Failed to load Roboto Mono font")
        else:
            print("Roboto Mono font loaded successfully")

        font_id_2 = QFontDatabase.addApplicationFont("Resources/fonts/Share_Tech/ShareTech_Regular.ttf")
        if font_id_2 == -2:
            print("Failed to load ShareTech font")
        else:
            print("ShareTech font loaded successfully")


        # Initial font size setup (10 is the default)
        self.starsFont = QFont("ShareTech", 10)

        # Connect the action to a function that changes the font

        

        # Set up menu bar
        self.menuBar = self.menuBar()

                # Font size menu
        font_menu = self.menuBar.addMenu("Font Size")
        fontTypeMenu = self.menuBar.addMenu("Font Type")

        # Create an action for the font type menu
        self.font_sharetech_action = QAction("ShareTech", self)
        self.font_default_action = QAction("Default", self)



        # Add action to the font type menu
        fontTypeMenu.addAction(self.font_sharetech_action)
        fontTypeMenu.addAction(self.font_default_action)




        # Connect the action to change self.starsFont instead of the system font
        self.font_sharetech_action.triggered.connect(lambda: self.set_stars_font("ShareTech", 10))
        self.font_default_action.triggered.connect(lambda: self.set_stars_font("Roboto Mono", 10))



        # Define actions for different font sizes
        self.font_8_action = QAction("8", self)
        self.font_8_action.triggered.connect(lambda: self.set_font_size(8))

        self.font_10_action = QAction("10", self)
        self.font_10_action.triggered.connect(lambda: self.set_font_size(10))

        self.font_12_action = QAction("12", self)
        self.font_12_action.triggered.connect(lambda: self.set_font_size(12))

        self.font_14_action = QAction("14", self)
        self.font_14_action.triggered.connect(lambda: self.set_font_size(14))


        # Add actions to the font size menu
        font_menu.addAction(self.font_8_action)
        font_menu.addAction(self.font_10_action)
        font_menu.addAction(self.font_12_action)
        font_menu.addAction(self.font_14_action)

        # Load TRACON configuration from an external file
        self.tracon_config = self.load_tracon_config(tracon_config)

        self.aircraft_positions = {}  # Store positions for each aircraft

        # Get TRACON names from GeoJSON files in Resources directory
        tracon_names = self.get_tracon_names_from_geojson_files()
        dialog = TraconSelectionDialog(tracon_names)

        if dialog.exec_() == QDialog.Accepted:
            selected_tracon = dialog.get_selected_tracon()

            # Ensure the selected TRACON exists, otherwise use a default like 'C90'
            if selected_tracon in self.tracon_config:
                self.tracon_config = self.tracon_config[selected_tracon]
            else:
                print(f"Selected TRACON {selected_tracon} not found, using default.")
                self.tracon_config = self.tracon_config.get("C90", {})  # Use default config (C90) if not found
        else:
            print("No TRACON selected. Exiting...")
            sys.exit()

        # Initialize radar settings and center after TRACON selection
        self.radar_lat, self.radar_lon = self.tracon_config["radar_settings"]["lat_lon"]
        self.scale_factor = self.tracon_config["radar_settings"]["scale_factor"]


        # Initialize offset
        self.offset = QPointF(0, 0)  # Initialize the offset for dragging/zooming
        self.dragging = False
        

        # Set the radar center based on screen geometry
        screen_geometry = self.screen().geometry()
        screen_center = screen_geometry.center()
        self.radar_center = QPointF(screen_center.x(), screen_center.y())  # Initialize radar_center

        self.geojson_loader = GeoJsonLoader()
        self.load_geojson_data(self.tracon_config["geojson_file"])

        # Other initialization continues...

        self.aircraft_data = []
        self.highlighted_states = {}        
        # Remove the call to self.load_aircraft_data()

        # Initialize the selected TRACON's display
        version = "v1.2.0"
        self.setWindowTitle(f"RadarView {version} :: {self.tracon_config['tracon_name']}")
        self.showMaximized()

        # Load GeoJSON for the selected TRACON
        try:
            with open(self.tracon_config["geojson_file"], "r") as f:
                geojson_data = json.load(f)
                self.geojson_loader.load(geojson_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load GeoJSON file: {e}")

        # Data fetcher setup (use the correct lat, lon, and distance)
        self.data_fetcher = DataFetcher(self.radar_lat, self.radar_lon, dist=100)  # Example: 150 miles distance
        self.data_fetcher.data_fetched.connect(self.update_aircraft_data)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.start_fetching_data)
        self.timer.start(2000)  # Fetch data every 5 seconds

        print(f"TRACONDisplay initialized for {self.tracon_config['tracon_name']}.")
        # Set central widget with layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        # Use a vertical layout to stack DCB and radar
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # DCB Strip on top
        self.dcbStrip = QWidget(self)
        self.dcbStrip.setFixedHeight(DCB_HEIGHT)
        self.dcbStrip.setStyleSheet("""
            background-color: #004d00;  /* Dark green background */
            border-bottom: 2px solid #00cc00;  /* Brighter green bottom border */
        """)

        # Button Strip inside DCB
        self.ButtonStrip = QWidget(self.dcbStrip)
        self.ButtonStrip.setStyleSheet("background-color: transparent;")
        button_layout = QGridLayout(self.ButtonStrip)
        button_layout.setSpacing(5)
        self.ButtonStrip.setLayout(button_layout)

        # Initialize button data and create buttons
        self.buttons_data = self.initialize_buttons_data()
        self.create_buttons




        # Add widgets to layout
        self.main_layout.addWidget(self.dcbStrip)      # DCB at the top

    def create_buttons(self, button_layout):
        # Define the custom layout pattern
        layout_pattern = [
            [0],             # 1
            [0, 1],          # 2
            [0],             # 1
            [0, 1],          # 2
            [0],             # 1
            [0, 1, 2],       # 222
            [0, 1, 2, 3, 4, 5, 6],  # 1111111
            [0, 1],          # 2
            [0, 1, 2, 3],    # 1111
            [0, 1],          # 2
            [0]              # 1
        ]

        button_index = 0  # Track buttons from buttons_data

        for row, cols in enumerate(layout_pattern):
            for col in cols:
                if button_index < len(self.buttons_data):
                    button_data = self.buttons_data[button_index]
                    button = QPushButton(button_data["text"], self.ButtonStrip)
                    button.setStyleSheet(f"""
                        QPushButton {{
                            background-color: #007f00;
                            color: white;
                            font-size: {FONT[1]}px;
                            padding: 8px 16px;
                            border-radius: 8px;
                            border: 2px solid #00cc00;
                            box-shadow: 2px 2px 5px #003300;
                        }}
                        QPushButton:pressed {{
                            background-color: #005f00;
                            border: 2px inset #009900;
                        }}
                        QPushButton:hover {{
                            background-color: #00b300;
                        }}
                    """)
                    button.clicked.connect(button_data["command"])
                    button_layout.addWidget(button, row, col)
                    button_index += 1




    def initialize_buttons_data(self):
        buttons_data = [
            {"text": "RANGE", "bg": "#3a3f40", "fg": "white", "command": self.button_1_action},
            {"text": "MAP REPOS", "bg": "#3a3f40", "fg": "white", "command": self.button_2_action},
            {"text": "UNDO", "bg": "#3a3f40", "fg": "white", "command": self.button_3_action},
            {"text": "PREF", "bg": "#3a3f40", "fg": "white", "command": self.button_4_action},
            {"text": "BRITE", "bg": "#3a3f40", "fg": "white", "command": self.button_5_action},
            {"text": "SAFETY LOGIC", "bg": "#3a3f40", "fg": "white", "command": self.button_6_action},
            {"text": "TOOLS", "bg": "#3a3f40", "fg": "white", "command": self.button_7_action},
            {"text": "VECTOR ON/OFF", "bg": "#3a3f40", "fg": "white", "command": self.button_8_action},
            {"text": "TEMP DATA", "bg": "#3a3f40", "fg": "white", "command": self.button_9_action},
            {"text": "DB AREA", "bg": "#3a3f40", "fg": "white", "command": self.button_10_action},
            {"text": "BUTTON", "bg": "#3a3f40", "fg": "white", "command": self.button_1_action},
            {"text": "BUTTON", "bg": "#3a3f40", "fg": "white", "command": self.button_2_action},
            {"text": "BUTTON", "bg": "#3a3f40", "fg": "white", "command": self.button_3_action},
            {"text": "BUTTON", "bg": "#3a3f40", "fg": "white", "command": self.button_4_action},
            {"text": "BUTTON", "bg": "#3a3f40", "fg": "white", "command": self.button_5_action}
        ]
        return buttons_data

    def create_buttons(self):
        for i, button_data in enumerate(self.buttons_data):
            button = QPushButton(button_data["text"], self.ButtonStrip)
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {button_data["bg"]};
                    color: {button_data["fg"]};
                    font-size: {FONT[1]}px;
                    padding: 6px 12px;
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    background-color: #555;
                }}
            """)
            button.clicked.connect(button_data["command"])
            self.ButtonStrip.layout().addWidget(button, i // 5, i % 5)  # Access layout directly

    def button_1_action(self):
        print("RANGE button clicked")

    def button_2_action(self):
        print("MAP REPOS button clicked")

    def button_3_action(self):
        print("UNDO button clicked")

    def button_4_action(self):
        print("PREF button clicked")

    def button_5_action(self):
        print("BRITE button clicked")

    def button_6_action(self):
        print("SAFETY LOGIC button clicked")

    def button_7_action(self):
        print("TOOLS button clicked")

    def button_8_action(self):
        print("VECTOR ON/OFF button clicked")

    def button_9_action(self):
        print("TEMP DATA button clicked")

    def button_10_action(self):
        print("DB AREA button clicked")

    def reset_view_action(self):
        self.offset = QPointF(0, 0)
        self.scale_factor = 1.0
        self.update()
        print("View reset")

    def zoom_in_action(self):
        self.scale_factor *= 1.2
        self.update()
        print("Zoomed in")

    def zoom_out_action(self):
        self.scale_factor /= 1.2
        self.update()
        print("Zoomed out")

    def refresh_data_action(self):
        self.start_fetching_data()
        print("Data refreshed")

    def exit_application_action(self):
        print("Exiting application")
        sys.exit()




    def set_stars_font(self, font_name, font_size):
        font = QFont(font_name, font_size)
        
        
        self.starsFont = font

        self.update




    def load_tracon_config(self, config_file):
        """Load TRACON configuration from an external JSON file."""
        try:
            with open(config_file, "r") as file:
                return json.load(file)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load TRACON configuration: {e}")
            sys.exit()

    def load_geojson_data(self, geojson_file):
        """Load GeoJSON data for the selected TRACON."""
        try:
            with open(geojson_file, "r") as file:
                geojson_data = json.load(file)
                self.geojson_loader.load(geojson_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load GeoJSON file: {e}")


    def get_tracon_names_from_geojson_files(self):
        """Retrieve available TRACON names from GeoJSON files."""
        tracon_names = []
        geojson_directory = r"Resources/tracons"
        
        for filename in os.listdir(geojson_directory):
            if filename.endswith(".geojson"):
                tracon_names.append(filename.replace(".geojson", ""))

        return tracon_names

    def draw_geojson_lines(self, painter):
        """Draw lines from the GeoJSON data with zoom and offset adjustments."""
        pen = QPen(QColor(255, 255, 255, 127))  # White lines with 50% transparency (alpha = 127)
        pen.setWidth(1)
        painter.setPen(pen)

        # Draw each line from the GeoJSON data
        for feature in self.geojson_loader.get_lines():
            coordinates = feature["geometry"]["coordinates"]
            for i in range(len(coordinates) - 1):
                # Map coordinates to radar coordinates and apply zoom/offset
                start_point = self.map_to_radar_coords(coordinates[i][1], coordinates[i][0])
                end_point = self.map_to_radar_coords(coordinates[i+1][1], coordinates[i+1][0])

                # If either of the points is out of bounds (0, 0), skip drawing
                if start_point == (0, 0) or end_point == (0, 0):
                    continue

                # Apply zoom and offset
                start_point = QPointF(self.radar_center.x() + start_point[0] * self.scale_factor + self.offset.x(),
                                    self.radar_center.y() - start_point[1] * self.scale_factor + self.offset.y())
                end_point = QPointF(self.radar_center.x() + end_point[0] * self.scale_factor + self.offset.x(),
                                    self.radar_center.y() - end_point[1] * self.scale_factor + self.offset.y())

                painter.drawLine(start_point, end_point)

    def start_fetching_data(self):
        if not self.data_fetcher.isRunning():
            self.data_fetcher.start()

    def update_aircraft_data(self, new_data):
        """Update the aircraft data and store positions for trails."""
        self.aircraft_data = new_data

        # Iterate over the new data
        for aircraft in new_data:
            aircraft_id = aircraft.get("flight", "N/A")
            lat = aircraft.get("lat")
            lon = aircraft.get("lon")

            # Ensure lat and lon are numeric
            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                print(f"ERROR: Non-numeric position data for aircraft {aircraft_id} (lat={lat}, lon={lon})")
                continue  # Skip this aircraft if conversion fails

            # Update position history if valid
            if aircraft_id not in self.aircraft_positions:
                self.aircraft_positions[aircraft_id] = deque(maxlen=8)  # Limit to last 8 positions
            self.aircraft_positions[aircraft_id].append((lat, lon))

            # Restore highlighted state
            highlighted = self.highlighted_states.get(aircraft_id, False)
            aircraft["highlighted"] = highlighted

        # Update radar display
        self.update()

    def set_font_size(self, size):
        """Set font size based on selected option."""
        self.starsFont.setPointSize(size)  # Update font size

        # Trigger a repaint to reflect font change
        self.update()

    def paintEvent(self, event):
        """Handle paint event to render radar, geoJSON, and aircraft trails."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))  # Black background

        # Apply updated font size before drawing
        painter.setFont(self.starsFont)  # Apply updated font

        self.draw_geojson_lines(painter)
        self.draw_radar(painter)
        self.draw_aircraft(painter)



    def draw_radar(self, painter):
        pen = QPen(QColor(200, 200, 200, 100))  # Grey-white rings
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(1, 10):
            painter.drawEllipse(self.radar_center + self.offset, i * 80 * self.scale_factor, i * 80 * self.scale_factor)


    def draw_aircraft(self, painter):
        for aircraft in self.aircraft_data:
            try:
                lat = aircraft.get("lat")
                lon = aircraft.get("lon")
                alt = aircraft.get("alt", 0)  # Default to 0 if 'alt' is not provided
                callsign = aircraft.get("flight", "N/A")
                speed = aircraft.get('gs', 0)
                if speed != "N/A":
                    speed = int(speed)
                else:
                    speed = 0  # Default speed if 'gs' is unavailable or invalid
                track = aircraft.get("track", 0)  # Track angle in degrees

                if isinstance(speed, str) and speed.lower() == "ground":
                    continue  # Skip this aircraft

                # Skip aircraft if altitude is non-numeric or indicates 'ground'
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    x, y = self.map_to_radar_coords(lat, lon)

                # Convert altitude to integer
                alt = int(alt)

                # Skip aircraft above 18,000 feet
                if alt > 18000:
                    continue

                # Validate data
                if lat is None or lon is None:
                    continue

                # Draw aircraft trail
                self.draw_aircraft_trail(aircraft, painter)

                # Map coordinates to radar screen
                x, y = self.map_to_radar_coords(lat, lon)
                x = self.radar_center.x() + (x * self.scale_factor) + self.offset.x()
                y = self.radar_center.y() - (y * self.scale_factor) + self.offset.y()

                # **Prediction Logic:**
                # Calculate the predicted position in 1 minute
                predicted_lat, predicted_lon = self.predict_position(lat, lon, track, speed)

                # Map predicted coordinates to radar screen
                predicted_x, predicted_y = self.map_to_radar_coords(predicted_lat, predicted_lon)
                predicted_x = self.radar_center.x() + (predicted_x * self.scale_factor) + self.offset.x()
                predicted_y = self.radar_center.y() - (predicted_y * self.scale_factor) + self.offset.y()


                # Calculate leader line endpoint
                leader_end_x = x  # Vertical line aligns with circle center
                leader_end_y = y - 20  # Adjust distance above the circle


                # Inside your drawing logic for aircraft, check if the aircraft is highlighted
                highlighted = aircraft.get("highlighted", False)

                # If highlighted, use a different text color
                if highlighted:
                    text_color = QColor(10,186,187)  # Blue color for highlighted aircraft
                else:
                    text_color = QColor(255, 255, 255)  # White color for non-highlighted aircraft

                painter.setFont(self.starsFont)  # Apply Roboto Mono font
                painter.setPen(text_color)

                # Draw the leader line

                painter.setPen(text_color)  # White leader line
                painter.drawLine(QPointF(x, y), QPointF(leader_end_x, leader_end_y))

                # Now draw the text with the appropriate color
                painter.setPen(text_color)
                painter.drawText(QPointF(leader_end_x + 5, leader_end_y - 5), callsign)
                painter.drawText(QPointF(leader_end_x + 5, leader_end_y + 10), f"{alt // 100:03} {speed}")



                # Draw the line from the blue aircraft dot to the predicted position
                painter.setPen(QPen(QColor(255, 255, 255), 1))  # White line with thickness 1
                painter.drawLine(QPointF(x, y), QPointF(predicted_x, predicted_y))  # Line from aircraft to predicted position

                circle_radius = 6
                painter.setBrush(QColor(31, 122, 255, 255))  # Blue color for aircraft
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(
                    QPointF(x, y),
                    circle_radius,
                    circle_radius
                )

            except Exception as e:
                print(f"Error drawing aircraft: {e}")
                
    def predict_position(self, lat, lon, heading, speed):
        # Earth's radius in meters
        R = 6371000  
        
        # Convert speed from knots to meters per second
        speed_mps = speed * 0.514444

        # Distance traveled in 1 minute
        distance = speed_mps * 60  

        # Convert heading to radians
        heading_rad = math.radians(heading)

        # Convert latitude and longitude to radians
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        # Predict new latitude
        predicted_lat_rad = math.asin(
            math.sin(lat_rad) * math.cos(distance / R) +
            math.cos(lat_rad) * math.sin(distance / R) * math.cos(heading_rad)
        )

        # Predict new longitude
        predicted_lon_rad = lon_rad + math.atan2(
            math.sin(heading_rad) * math.sin(distance / R) * math.cos(lat_rad),
            math.cos(distance / R) - math.sin(lat_rad) * math.sin(predicted_lat_rad)
        )

        # Convert back to degrees
        predicted_lat = math.degrees(predicted_lat_rad)
        predicted_lon = math.degrees(predicted_lon_rad)

        return predicted_lat, predicted_lon

    def draw_aircraft_trail(self, aircraft, painter):
        """Draw the trail for the aircraft."""
        aircraft_id = aircraft.get("flight", "N/A")
        if aircraft_id not in self.aircraft_positions:
            return

        # Get the last positions of the aircraft in reverse order (newest first)
        positions = list(self.aircraft_positions[aircraft_id])[::-1]

        # Draw circles for the trail
        for i, (lat, lon) in enumerate(positions):
            # Map the coordinates to radar screen
            x, y = self.map_to_radar_coords(lat, lon)
            x = self.radar_center.x() + (x * self.scale_factor) + self.offset.x()
            y = self.radar_center.y() - (y * self.scale_factor) + self.offset.y()

            # Adjust color intensity for fading effect
            # The first circle is fully blue, and the color fades with each older position
            alpha_value = max(255 - i * 30, 50)  # Fade effect, stops at a certain opacity
            color = QColor(27,110,224, alpha_value)  # Blue with fading alpha

            painter.setBrush(color)
            painter.setPen(Qt.NoPen)

            # Draw the trail circle
            painter.drawEllipse(QPointF(x, y), 4, 4)  # Smaller circles for the trail

    def map_to_radar_coords(self, lat, lon):
        """Map latitude and longitude to radar coordinates."""
        
        # Check if lat and lon are not sequences (lists or tuples)
        if isinstance(lat, (list, tuple)) or isinstance(lon, (list, tuple)):
            print(f"ERROR: lat or lon is a sequence (lat={lat}, lon={lon})")
            return 0, 0  # Return early if the values are invalid

        # Ensure lat and lon are floats
        lat = float(lat)
        lon = float(lon)

        # Calculate distance from radar center
        center_lat, center_lon = self.radar_lat, self.radar_lon
        distance = self.haversine(center_lat, center_lon, lat, lon)

        if distance > 200 * 1609.34:  # Ignore coordinates farther than 200 miles (in meters)
            return 0, 0  # Return a value outside the radar view

        scale = 800  # Adjust the scale for your coordinate system
        x = (lon - center_lon) * scale * math.cos(math.radians(center_lat))  # Adjust for latitude
        y = (lat - center_lat) * scale
        return x, y


        
    def assign_sector(self, lat, lon, alt):
        """Assign aircraft to a TRACON sector based on position or altitude."""
        if alt < 10000:
            return "F"
        elif 10000 <= alt < 20000:
            return "V"
        elif 20000 <= alt < 30000:
            return "A"
        else:
            return "H"


    def haversine(self, lat1, lon1, lat2, lon2):
        """Calculate the distance in meters between two lat/lon points."""
        R = 6371000  # Radius of the Earth in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2) * math.sin(delta_phi / 2) + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) * math.sin(delta_lambda / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c  # Distance in meters
        return distance
    
    def mouseMoveEvent(self, event):
        """Handle mouse move event for dragging."""
        if self.dragging:
            delta = event.pos() - self.last_pos
            self.offset += delta
            self.last_pos = event.pos()
            self.update()


    def mouseReleaseEvent(self, event):
        """Handle mouse release event."""
        if event.button() == Qt.LeftButton:
            self.dragging = False

    def wheelEvent(self, event):
        """Zoom in or out on the display based on the mouse position."""
        zoom_in = event.angleDelta().y() > 0

        # Check if the CTRL key is held down
        ctrl_held = event.modifiers() & Qt.ControlModifier

        # Adjust zoom factor if CTRL is held down
        if ctrl_held:
            zoom_factor = 1.7 if zoom_in else 0.5  # Zoom twice as fast when CTRL is held
        else:
            zoom_factor = 1.1 if zoom_in else 0.9  # Regular zoom factor

        self.zoom_at(event.pos(), zoom_factor)

    def zoom_at(self, mouse_pos, zoom_factor):
        """Zoom based on the mouse position."""
        mouse_x = mouse_pos.x()
        mouse_y = mouse_pos.y()

        # Calculate the current mouse position in the radar's coordinate system
        mouse_radar_x = mouse_x - self.radar_center.x() - self.offset.x()
        mouse_radar_y = mouse_y - self.radar_center.y() - self.offset.y()

        # Apply the zoom factor
        self.scale_factor *= zoom_factor

        # Recalculate the offset based on the zoom center (mouse position)
        self.offset.setX(self.offset.x() - mouse_radar_x * (zoom_factor - 1))
        self.offset.setY(self.offset.y() - mouse_radar_y * (zoom_factor - 1))

        self.update()


    def mousePressEvent(self, event):
        """Handle mouse press event for dragging and CTRL+click interaction."""
        if event.button() == Qt.LeftButton:
            # Handle dragging
            self.last_pos = event.pos()
            self.dragging = True
        
        elif event.button() == Qt.LeftButton:
            self.update_display()

        # Handle CTRL + Click (Middle button click for aircraft selection)
        elif event.button() == Qt.MiddleButton:
            click_pos = event.pos()
            for aircraft in self.aircraft_data:
                lat = aircraft.get("lat")
                lon = aircraft.get("lon")
                x, y = self.map_to_radar_coords(lat, lon)
                x = self.radar_center.x() + (x * self.scale_factor) + self.offset.x()
                y = self.radar_center.y() - (y * self.scale_factor) + self.offset.y()

                # Check if click is within the circle's radius
                circle_radius = 15
                if (click_pos.x() - x) ** 2 + (click_pos.y() - y) ** 2 <= circle_radius ** 2:
                    # Toggle highlighted state
                    callsign = aircraft.get("flight")
                    if callsign:
                        aircraft["highlighted"] = not aircraft.get("highlighted", False)
                        self.highlighted_states[callsign] = aircraft["highlighted"]
                    self.update()  # Refresh the UI
                    break
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showMaximized()
            else:
                self.showFullScreen()



if __name__ == "__main__":
    app = QApplication(sys.argv)

    tracon_config_file = r"Resources/.TraconConfig"

    # Initialize and show the TRACON display
    radar_display = TRACONDisplay(tracon_config_file)
    radar_display.show()

    sys.exit(app.exec_())
