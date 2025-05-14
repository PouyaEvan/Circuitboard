import sys
import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QToolBar, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
                             QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsTextItem,
                             QGraphicsItemGroup, QMenu, QInputDialog, QMessageBox,
                             QGraphicsPathItem, QFileDialog, QDockWidget, QListWidget,
                             QLabel, QLineEdit, QFormLayout, QPushButton, QCheckBox)
from PyQt6.QtGui import (QAction, QIcon, QPainter, QPen, QBrush, QColor, QFont,
                         QTransform, QFontMetrics, QPainterPath, QKeySequence)
from PyQt6.QtCore import Qt, QPointF
import math

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: NumPy not found. Some resistor features will be limited.")

from config import *

def get_resistor_color_code(resistance):
    if not NUMPY_AVAILABLE:
        return ["black", "black", "black", "gold"]
        
    if resistance <= 0:
        return ["black", "black", "black", "gold"]

    magnitude = int(np.floor(np.log10(abs(resistance)) / 3) * 3)
    if magnitude < -2: 
        magnitude = -2

    base_value = resistance / (10**magnitude)

    digit1 = int(np.floor(base_value))
    digit2_raw = round((base_value - digit1) * 10)

    if digit2_raw == 10:
        digit2_raw = 0
        digit1 += 1
        if digit1 == 10:
            digit1 = 1
            magnitude += 1

    digit1 = max(0, min(9, digit1))
    digit2 = max(0, min(9, digit2_raw))

    multiplier_value = 10**magnitude
    closest_multiplier_color = "black"
    min_diff = float('inf')
    for val, color in RESISTOR_MULTIPLIER_MAP.items():
        if abs(val - multiplier_value) < min_diff:
            min_diff = abs(val - multiplier_value)
            closest_multiplier_color = color

    tolerance_color = "gold"  # 5% tolerance as default

    color1 = RESISTOR_VALUE_MAP.get(digit1, "black")
    color2 = RESISTOR_VALUE_MAP.get(digit2, "black")
    color3 = closest_multiplier_color
    color4 = tolerance_color

    return [color1, color2, color3, color4]


class Resistor(Component):
    def __init__(self, name="R", position=QPointF(0, 0), resistance=1000.0):
        super().__init__(name, position)
        self.component_type = "Resistor"
        self.resistance = resistance

        self.body_width = GRID_SIZE * 4
        self.body_height = GRID_SIZE * 1.5

        self.body = QGraphicsRectItem(0, -self.body_height/2, self.body_width, self.body_height, self)
        self.body.setBrush(QBrush(Qt.GlobalColor.white))
        self.body.setPen(QPen(Qt.GlobalColor.black, 2))

        lead_length = GRID_SIZE
        lead1 = QGraphicsLineItem(-lead_length, 0, 0, 0, self)
        lead1.setPen(QPen(Qt.GlobalColor.black, 2))

        lead2 = QGraphicsLineItem(self.body_width, 0, self.body_width + lead_length, 0, self)
        lead2.setPen(QPen(Qt.GlobalColor.black, 2))

        pin_in = self.add_pin(-lead_length, 0, "in")
        pin_out = self.add_pin(self.body_width + lead_length, 0, "out")

        # Create label and update text to include value
        self.create_label(name, x_offset=self.body_width/2, y_offset=-self.body_height/2)
        self.update_label_text()

        self._color_bands = []
        self.update_color_bands()

    def get_properties(self):
        properties = super().get_properties()
        properties["Resistance"] = self.resistance
        return properties

    def set_property(self, name, value):
        if super().set_property(name, value):
            return True
        if name == "Resistance":
            try:
                new_resistance = float(value)
                if new_resistance > 0:
                    self.resistance = new_resistance
                    self.update_label_text()
                    self.update_color_bands()
                    return True
                else:
                    QMessageBox.warning(None, "Input Error", "Resistance must be positive.")
                    return False
            except ValueError:
                QMessageBox.warning(None, "Input Error", "Resistance must be a number.")
                return False
        return False

    def update_label_text(self):
        if self.label_item:
            if abs(self.resistance) >= 1e6:
                display_value = self.resistance / 1e6
                unit = "MΩ"
            elif abs(self.resistance) >= 1e3:
                display_value = self.resistance / 1e3
                unit = "kΩ"
            else:
                display_value = self.resistance
                unit = "Ω"
            
            self.label_item.setPlainText(f"{self.component_name} ({display_value:.2f}{unit})")
            
            # Re-center label
            label_rect = self.label_item.boundingRect()
            current_pos = self.label_item.pos()
            new_x = self.body_width/2 - label_rect.width()/2
            self.label_item.setPos(new_x, current_pos.y())

    def update_color_bands(self):
        # Remove existing color bands
        for band in self._color_bands:
            self.scene().removeItem(band) if band.scene() else None
        self._color_bands.clear()

        # Get color code
        colors = get_resistor_color_code(self.resistance)
        if not colors or len(colors) != 4:
            return  # Invalid color code

        # Create new bands
        band_width = self.body_width / 10
        band_height = self.body_height * 0.8
        band_y = -band_height / 2

        band_positions_x = [
            self.body_width * 0.15,
            self.body_width * 0.3,
            self.body_width * 0.55,
            self.body_width * 0.8
        ]

        # Create bands with proper colors
        for i, color_name in enumerate(colors):
            color = QColor(color_name)
            if not color.isValid():  # Fallback for named colors
                color_map = {
                    "black": QColor(0, 0, 0),
                    "brown": QColor(139, 69, 19),
                    "red": QColor(255, 0, 0),
                    "orange": QColor(255, 165, 0),
                    "yellow": QColor(255, 255, 0),
                    "green": QColor(0, 128, 0),
                    "blue": QColor(0, 0, 255),
                    "violet": QColor(138, 43, 226),
                    "grey": QColor(128, 128, 128),
                    "white": QColor(255, 255, 255),
                    "gold": QColor(255, 215, 0),
                    "silver": QColor(192, 192, 192)
                }
                color = color_map.get(color_name, QColor(0, 0, 0))
            
            # Create band
            band = QGraphicsRectItem(
                band_positions_x[i], band_y,
                band_width, band_height,
                self
            )
            band.setBrush(QBrush(color))
            band.setPen(QPen(Qt.GlobalColor.black, 0.5))
            self._color_bands.append(band)

    def to_dict(self):
        data = super().to_dict()
        data["properties"]["Resistance"] = self.resistance
        return data
