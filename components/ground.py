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
            self.label_item.setPos(new_x, current_pos.y())    def to_dict(self):
        data = super().to_dict()
        return data
