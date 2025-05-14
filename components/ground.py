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
from PyQt6.QtCore import Qt

from config import *
from config import Component



class Ground(Component):
    def __init__(self, name="GND", position=QPointF(0, 0)):
        super().__init__(name, position)
        self.component_type = "Ground"

        line1 = QGraphicsLineItem(0, -GRID_SIZE, 0, 0, self)
        line1.setPen(QPen(Qt.GlobalColor.black, 2))

        line2 = QGraphicsLineItem(-GRID_SIZE, 0, GRID_SIZE, 0, self)
        line2.setPen(QPen(Qt.GlobalColor.black, 2))

        line3 = QGraphicsLineItem(-GRID_SIZE * 0.7, GRID_SIZE * 0.5, GRID_SIZE * 0.7, GRID_SIZE * 0.5, self)
        line3.setPen(QPen(Qt.GlobalColor.black, 2))

        line4 = QGraphicsLineItem(-GRID_SIZE * 0.4, GRID_SIZE, GRID_SIZE * 0.4, GRID_SIZE, self)
        line4.setPen(QPen(Qt.GlobalColor.black, 2))

        pin = self.add_pin(0, -GRID_SIZE, "ground")

        self.create_label(name, x_offset=0, y_offset=GRID_SIZE * 1.5)
        self.update_label_text()

    def get_properties(self):
        return super().get_properties()

    def set_property(self, name, value):
        if super().set_property(name, value):
            return True
        return False

    def update_label_text(self):
        # For Ground, the label is just the name
        if self.label_item:
            self.label_item.setPlainText(self.component_name)
            
            # Center the label
            label_rect = self.label_item.boundingRect()
            current_pos = self.label_item.pos()
            new_x = 0 - label_rect.width()/2
            self.label_item.setPos(new_x, current_pos.y())

    def to_dict(self):
        data = super().to_dict()
        return data

class Capacitor(Component):
    def __init__(self, name="C", position=QPointF(0, 0), capacitance=1e-6):
        super().__init__(name, position)
        self.component_type = "Capacitor"
        self.capacitance = capacitance

        plate_height = GRID_SIZE * 2
        plate_separation = GRID_SIZE * 1.5
        lead_length = GRID_SIZE * 2.25

        plate1 = QGraphicsLineItem(0, -plate_height/2, 0, plate_height/2, self)
        plate1.setPen(QPen(Qt.GlobalColor.black, 3))

        plate2 = QGraphicsLineItem(plate_separation, -plate_height/2, plate_separation, plate_height/2, self)
        plate2.setPen(QPen(Qt.GlobalColor.black, 3))

        lead1 = QGraphicsLineItem(-lead_length, 0, 0, 0, self)
        lead1.setPen(QPen(Qt.GlobalColor.black, 2))

        lead2 = QGraphicsLineItem(plate_separation, 0, plate_separation + lead_length, 0, self)
        lead2.setPen(QPen(Qt.GlobalColor.black, 2))

        pin_in = self.add_pin(-lead_length, 0, "in")
        pin_out = self.add_pin(plate_separation + lead_length, 0, "out")

        # Create label and update text to include value
        self.create_label(name, x_offset=plate_separation/2, y_offset=-plate_height/2 - 5)
        self.update_label_text()


    def get_properties(self):
        properties = super().get_properties()
        properties["Capacitance"] = self.capacitance
        return properties

    def set_property(self, name, value):
        if super().set_property(name, value):
            return True
        if name == "Capacitance":
            try:
                new_capacitance = float(value)
                if new_capacitance >= 0:
                    self.capacitance = new_capacitance
                    self.update_label_text()
                    return True
                else:
                    QMessageBox.warning(None, "Input Error", "Capacitance cannot be negative.")
                    return False
            except ValueError:
                QMessageBox.warning(None, "Input Error", "Capacitance must be a number.")
                return False
        return False

    def update_label_text(self):
        if self.label_item:
            if abs(self.capacitance) >= 1e-6:
                  display_value = self.capacitance * 1e6
                  unit = "μF"
            elif abs(self.capacitance) >= 1e-9:
                  display_value = self.capacitance * 1e9
                  unit = "nF"
            elif abs(self.capacitance) >= 1e-12:
                  display_value = self.capacitance * 1e12
                  unit = "pF"
            else:
                  display_value = self.capacitance
                  unit = "F"

            self.label_item.setPlainText(f"{self.component_name} ({display_value:.2f}{unit})")
            label_rect = self.label_item.boundingRect()
            current_pos = self.label_item.pos()
            plate_separation = GRID_SIZE * 1.5
            x_offset_original = plate_separation/2
            new_x = x_offset_original - label_rect.width()/2
            self.label_item.setPos(new_x, current_pos.y())


    def to_dict(self):
        data = super().to_dict()
        data["properties"]["Capacitance"] = self.capacitance
        return data
