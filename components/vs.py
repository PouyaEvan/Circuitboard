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

from config import *
from config import Component

class VoltageSource(Component):
    def __init__(self, name="V", position=QPointF(0, 0), voltage=5.0):
        super().__init__(name, position)
        self.component_type = "VoltageSource"
        self.voltage = voltage

        width = GRID_SIZE * 4
        height = GRID_SIZE * 2

        body = QGraphicsRectItem(0, -height/2, width, height, self)
        body.setBrush(QBrush(Qt.GlobalColor.white))
        body.setPen(QPen(Qt.GlobalColor.black, 2))

        symbol_spacing_x = GRID_SIZE * 2
        symbol_length = GRID_SIZE * 0.8

        plus_h = QGraphicsLineItem(-symbol_length/2, 0, symbol_length/2, 0, self)
        plus_v = QGraphicsLineItem(0, -symbol_length/2, 0, symbol_length/2, self)

        minus_h = QGraphicsLineItem(-symbol_length/2, 0, symbol_length/2, 0, self)

        plus_pen = QPen(Qt.GlobalColor.black, 2)
        minus_pen = QPen(Qt.GlobalColor.black, 2)
        plus_h.setPen(plus_pen)
        plus_v.setPen(plus_pen)
        minus_h.setPen(minus_pen)

        plus_group = QGraphicsItemGroup(self)
        plus_group.addToGroup(plus_h)
        plus_group.addToGroup(plus_v)
        plus_group.setPos(width/2 - symbol_spacing_x/2, 0)

        minus_h.setPos(width/2 + symbol_spacing_x/2, 0)

        lead_length = GRID_SIZE
        lead_pos = QGraphicsLineItem(width, 0, width + lead_length, 0, self)
        lead_pos.setPen(QPen(Qt.GlobalColor.black, 2))

        lead_neg = QGraphicsLineItem(-lead_length, 0, 0, 0, self)
        lead_neg.setPen(QPen(Qt.GlobalColor.black, 2))

        pin_pos = self.add_pin(width + lead_length, 0, "+")
        pin_neg = self.add_pin(-lead_length, 0, "-")

        # Create label and update text to include value
        self.create_label(name, x_offset=width/2, y_offset=-height/2)
        self.update_label_text()

    def get_properties(self):
        properties = super().get_properties()
        properties["Voltage"] = self.voltage
        return properties

    def set_property(self, name, value):
        if super().set_property(name, value):
            return True
        if name == "Voltage":
            try:
                self.voltage = float(value)
                self.update_label_text()
                return True
            except ValueError:
                QMessageBox.warning(None, "Input Error", "Voltage must be a number.")
                return False
        return False

    def update_label_text(self):
        if self.label_item:
            abs_v = abs(self.voltage)
            if abs_v >= 1:
                display_value = self.voltage
                unit = "V"
            elif abs_v >= 1e-3:
                display_value = self.voltage * 1e3
                unit = "mV"
            elif abs_v >= 1e-6:
                display_value = self.voltage * 1e6
                unit = "μV"
            else:
                display_value = self.voltage
                unit = "V"
            self.label_item.setPlainText(f"{self.component_name} ({display_value:.2f}{unit})")
            label_rect = self.label_item.boundingRect()
            current_pos = self.label_item.pos()
            width = GRID_SIZE * 4
            x_offset_original = width/2
            new_x = x_offset_original - label_rect.width()/2
            self.label_item.setPos(new_x, current_pos.y())

    def to_dict(self):
        data = super().to_dict()
        data["properties"]["Voltage"] = self.voltage
        return data