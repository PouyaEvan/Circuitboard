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


class Wire(QGraphicsPathItem):
    def __init__(self, start_pin, end_pin, parent=None):
        super().__init__(parent)
        self.start_pin = start_pin
        self.end_pin = end_pin
        self.setPen(WIRE_PEN)
        self.setZValue(WIRE_Z_VALUE)
        self.setFlags(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self._points = [start_pin.scenePos(), end_pin.scenePos()] # Store points for orthogonal routing

        self.start_comp = start_pin.data(2)
        self.end_comp = end_pin.data(2)

        if self.start_comp: self.start_comp.add_connected_wire(self)
        if self.end_comp: self.end_comp.add_connected_wire(self)

        self.update_positions()

    def update_positions(self):
        if self.start_pin and self.end_pin:
            start_pos = self.start_pin.scenePos()
            end_pos = self.end_pin.scenePos()

            scene = self.scene()
            if scene and scene.views():
                canvas = scene.views()[0]
                if hasattr(canvas, 'generate_orthogonal_points'):
                    # Generate orthogonal points based on current pin positions
                    self._points = canvas.generate_orthogonal_points(start_pos, end_pos)
                else:
                    print("Warning: Could not access orthogonal routing. Using straight wire.")
                    self._points = [start_pos, end_pos]
            else:
                print("Warning: Scene or views not available for routing. Using straight wire.")
                self._points = [start_pos, end_pos]

            path = QPainterPath()
            if self._points:
                path.moveTo(self._points[0])
                for i in range(1, len(self._points)):
                    path.lineTo(self._points[i])
            self.setPath(path)
        else:
            self.setPath(QPainterPath())

    def remove(self):
        print(f"Wire.remove() called for {self}")
        scene = self.scene()
        if not scene:
            print("Wire has no scene in remove(), cannot proceed.")
            return

        if self.start_comp: self.start_comp.remove_connected_wire(self)
        if self.end_comp: self.end_comp.remove_connected_wire(self)

        if hasattr(scene, 'views') and scene.views():
            main_window = scene.views()[0].main_window
            if main_window and hasattr(main_window, 'netlist'):
                print("Calling netlist.remove_wire from Wire.remove()")
                main_window.netlist.remove_wire(self)
            else:
                print("Could not access main_window or netlist from Wire.remove()")

        print("Wire.remove() finished.")
        scene.removeItem(self)

    def to_dict(self):
        start_comp_name = self.start_comp.component_name if self.start_comp else None
        start_pin_name = self.start_pin.data(1) if self.start_pin else None
        end_comp_name = self.end_comp.component_name if self.end_comp else None
        end_pin_name = self.end_pin.data(1) if self.end_pin else None

        data = {
            "start_pin": {
                "component": start_comp_name,
                "pin": start_pin_name
            },
            "end_pin": {
                "component": end_comp_name,
                "pin": end_pin_name
            },
            "points": [{"x": p.x(), "y": p.y()} for p in self._points] # Save intermediate points
        }
        return data

