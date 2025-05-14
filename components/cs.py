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

from Cconfig import *


class CurrentSource(Component):
    def __init__(self, name="I", position=QPointF(0, 0), current=1.0):
        super().__init__(name, position)
        self.component_type = "CurrentSource"
        self.current = current

        width = GRID_SIZE * 4
        height = GRID_SIZE * 2

        body = QGraphicsEllipseItem(0, -height/2, width, height, self) # Circle body
        body.setBrush(QBrush(Qt.GlobalColor.white))
        body.setPen(QPen(Qt.GlobalColor.black, 2))

        # Arrow inside the circle
        arrow_length = GRID_SIZE * 1.5
        arrow_head_size = GRID_SIZE * 0.5

        # Line for the arrow shaft
        arrow_shaft = QGraphicsLineItem(width/2 - arrow_length/2, 0, width/2 + arrow_length/2, 0, self)
        arrow_shaft.setPen(QPen(Qt.GlobalColor.black, 2))

        # Arrow head (triangle)
        arrow_head_path = QPainterPath()
        arrow_head_path.moveTo(width/2 + arrow_length/2, 0)
        arrow_head_path.lineTo(width/2 + arrow_length/2 - arrow_head_size, -arrow_head_size/2)
        arrow_head_path.lineTo(width/2 + arrow_length/2 - arrow_head_size, arrow_head_size/2)
        arrow_head_path.closeSubpath()
        arrow_head = QGraphicsPathItem(arrow_head_path, self)
        arrow_head.setBrush(QBrush(Qt.GlobalColor.black))
        arrow_head.setPen(QPen(Qt.GlobalColor.black, 1))

        lead_length = GRID_SIZE
        lead_pos = QGraphicsLineItem(width, 0, width + lead_length, 0, self) # + terminal lead
        lead_pos.setPen(QPen(Qt.GlobalColor.black, 2))

        lead_neg = QGraphicsLineItem(-lead_length, 0, 0, 0, self) # - terminal lead
        lead_neg.setPen(QPen(Qt.GlobalColor.black, 2))

        pin_pos = self.add_pin(width + lead_length, 0, "+")
        pin_neg = self.add_pin(-lead_length, 0, "-")

        # Create label and update text to include value
        self.create_label(name, x_offset=width/2, y_offset=-height/2)
        self.update_label_text()

    def get_properties(self):
        properties = super().get_properties()
        properties["Current"] = self.current
        return properties

    def set_property(self, name, value):
        if super().set_property(name, value):
            return True
        if name == "Current":
            try:
                self.current = float(value)
                self.update_label_text()
                return True
            except ValueError:
                QMessageBox.warning(None, "Input Error", "Current must be a number.")
                return False
        return False

    def update_label_text(self):
        if self.label_item:
            self.label_item.setPlainText(f"{self.component_name} ({self.current}A)")
            
            # Re-center label
            label_rect = self.label_item.boundingRect()
            current_pos = self.label_item.pos()
            width = GRID_SIZE * 4
            x_offset_original = width/2
            new_x = x_offset_original - label_rect.width()/2
            self.label_item.setPos(new_x, current_pos.y())

    def to_dict(self):
        data = super().to_dict()
        data["properties"]["Current"] = self.current
        return data
