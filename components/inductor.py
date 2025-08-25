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

from config import *
from config import Component

class Inductor(Component):
    def __init__(self, name="L", position=QPointF(0, 0), inductance=1e-3):
        super().__init__(name, position)
        self.component_type = "Inductor"
        self.inductance = inductance

        body_width = GRID_SIZE * 4
        lead_length = GRID_SIZE

        # Inductor coils: draw proper coil symbol with upward semicircles
        coil_count = 4
        coil_width = body_width / coil_count
        coil_radius = coil_width / 2
        coil_height = GRID_SIZE * 0.6  # Height of each coil
        
        coil_path = QPainterPath()
        # Start at the left connection point
        coil_path.moveTo(0, 0)
        
        # Draw each coil as an upward semicircle
        for i in range(coil_count):
            start_x = i * coil_width
            end_x = start_x + coil_width
            center_x = start_x + coil_radius
            
            # Draw semicircle from bottom-left to bottom-right, arcing upward
            rect = QPointF(start_x, -coil_height), QPointF(end_x, 0)
            coil_path.arcTo(start_x, -coil_height, coil_width, coil_height * 2, 180, 180)

        coil_item = QGraphicsPathItem(coil_path, self)
        coil_item.setPen(QPen(Qt.GlobalColor.black, 2))
        coil_item.setPos(0, 0)  # Position coils at the origin

        lead1 = QGraphicsLineItem(-lead_length, 0, 0, 0, self)
        lead1.setPen(QPen(Qt.GlobalColor.black, 2))

        lead2 = QGraphicsLineItem(body_width, 0, body_width + lead_length, 0, self)
        lead2.setPen(QPen(Qt.GlobalColor.black, 2))

        pin_in = self.add_pin(-lead_length, 0, "in")
        pin_out = self.add_pin(body_width + lead_length, 0, "out")

        # Create label and update text to include value
        self.create_label(name, x_offset=body_width / 2, y_offset=-coil_height - 10)
        self.update_label_text()

    def get_properties(self):
        properties = super().get_properties()
        properties["Inductance"] = self.inductance
        return properties

    def set_property(self, name, value):
        if super().set_property(name, value):
            return True
        if name == "Inductance":
            try:
                new_inductance = float(value)
                if new_inductance > 0:
                    self.inductance = new_inductance
                    self.update_label_text()
                    return True
                else:
                    QMessageBox.warning(None, "Input Error", "Inductance must be positive.")
                    return False
            except ValueError:
                QMessageBox.warning(None, "Input Error", "Inductance must be a number.")
                return False
        return False

    def update_label_text(self):
        if self.label_item:
            abs_l = abs(self.inductance)
            if abs_l >= 1:
                display_value = self.inductance
                unit = "H"
            elif abs_l >= 1e-3:
                display_value = self.inductance * 1e3
                unit = "mH"
            elif abs_l >= 1e-6:
                display_value = self.inductance * 1e6
                unit = "μH"
            elif abs_l >= 1e-9:
                display_value = self.inductance * 1e9
                unit = "nH"
            else:
                display_value = self.inductance
                unit = "H"
            self.label_item.setPlainText(f"{self.component_name} ({display_value:.2f}{unit})")
            label_rect = self.label_item.boundingRect()
            current_pos = self.label_item.pos()
            body_width = GRID_SIZE * 4
            lead_length = GRID_SIZE
            x_offset_original = lead_length + body_width/2
            new_x = x_offset_original - label_rect.width()/2
            self.label_item.setPos(new_x, current_pos.y())

    def to_dict(self):
        data = super().to_dict()
        data["properties"]["Inductance"] = self.inductance
        return data
