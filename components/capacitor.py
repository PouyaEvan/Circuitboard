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

class Component(QGraphicsItemGroup):
    def __init__(self, name="Comp", position=QPointF(0, 0), parent=None):
        super().__init__(parent)
        self.component_name = name
        self.setPos(position)
        self.setFlags(QGraphicsItemGroup.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItemGroup.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItemGroup.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(COMPONENT_Z_VALUE)
        self._pins = []
        self.connected_wires = []
        self.label_item = None
        self.component_type = "Generic"
        self.current_text_items = []


    def add_pin(self, x, y, name=""):
        pin = QGraphicsEllipseItem(-PIN_SIZE/2, -PIN_SIZE/2, PIN_SIZE, PIN_SIZE, self)
        pin.setPos(x, y)
        pin.setBrush(QBrush(PIN_COLOR_DEFAULT))
        pin.setPen(QPen(Qt.GlobalColor.black, 1))
        pin.setData(0, "pin")
        pin.setData(1, name)
        pin.setData(2, self)
        pin.setData(3, None)
        self._pins.append(pin)
        return pin

    def get_pins(self):
        return self._pins

    def create_label(self, text, x_offset=0, y_offset=0):
        self.label_item = QGraphicsTextItem(text, self)
        self.label_item.setFont(LABEL_FONT)
        self.label_item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations)

        label_rect = self.label_item.boundingRect()
        self.label_item.setPos(x_offset - label_rect.width()/2, y_offset - label_rect.height())

    def set_name(self, name):
        old_name = self.component_name
        self.component_name = name
        if self.label_item:
            self.update_label_text()

        if hasattr(self.scene(), 'views') and self.scene().views():
            main_window = self.scene().views()[0].main_window
            if main_window:
                main_window.deregister_component_name(self.component_type[0], old_name)
                main_window.register_component_name(self.component_type[0], name)

    def itemChange(self, change, value):
        if change == QGraphicsItemGroup.GraphicsItemChange.ItemPositionChange:
            # Snap to grid if enabled
            scene = self.scene()
            if scene and hasattr(scene, 'views') and scene.views():
                view = scene.views()[0]
                if hasattr(view, 'snap_to_grid_enabled') and view.snap_to_grid_enabled:
                    grid_size = GRID_SIZE
                    x = round(value.x() / grid_size) * grid_size
                    y = round(value.y() / grid_size) * grid_size
                    return QPointF(x, y)

        if change == QGraphicsItemGroup.GraphicsItemChange.ItemPositionHasChanged:
            # Update connected wires when component moves
            for wire in self.connected_wires:
                if wire.scene():
                    wire.update_positions()

        return super().itemChange(change, value)

    def rotate(self, angle):
        current_rotation = self.rotation()
        new_rotation = current_rotation + angle
        center = self.boundingRect().center()
        self.setTransformOriginPoint(center)
        self.setRotation(new_rotation)
        print(f"Rotated {self.component_name} to {new_rotation} degrees.")

        # Update connected wires and label position after rotation
        for wire in self.connected_wires:
            if wire.scene():
                wire.update_positions()
            
        if self.label_item:
            self.update_label_text()

    def remove(self):
        print(f"Component.remove() called for {self.component_name}")
        scene = self.scene()
        if not scene:
            print("Component has no scene in remove(), cannot proceed.")
            return

        # Disconnect and remove all connected wires
        connected_wires = list(self.connected_wires)  # Create a copy to avoid modification during iteration
        for wire in connected_wires:
            if wire.scene():
                wire.remove()
        
        # Clear hover state if this component's pin is being hovered
        if hasattr(scene, 'views') and scene.views():
            for view in scene.views():
                if hasattr(view, 'hovered_pin'):
                    if view.hovered_pin and view.hovered_pin in self._pins:
                        view.hovered_pin = None

        # Deregister from main window and netlist
        if hasattr(scene, 'views') and scene.views():
            main_window = scene.views()[0].main_window
            if main_window:
                main_window.deregister_component_name(self.component_type[0], self.component_name)
                if hasattr(main_window, 'netlist'):
                    main_window.netlist.remove_component(self)

        # Remove current display items
        for item in self.current_text_items:
            if item.scene():
                item.scene().removeItem(item)
        self.current_text_items.clear()

        # Remove the component itself
        scene.removeItem(self)
        print(f"Component {self.component_name} removed successfully.")

    def add_connected_wire(self, wire):
        if wire not in self.connected_wires:
            self.connected_wires.append(wire)

    def remove_connected_wire(self, wire):
        if wire in self.connected_wires:
            self.connected_wires.remove(wire)
            print(f"Removed wire from {self.component_name}'s connected_wires.")
        else:
            print(f"Wire not found in {self.component_name}'s connected_wires.")

    def get_properties(self):
        return {"Name": self.component_name}

    def set_property(self, name, value):
        if name == "Name":
            self.set_name(value)
            return True
        return False

    def update_label_text(self):
        if self.label_item:
            self.label_item.setPlainText(self.component_name)

    def to_dict(self):
        return {
            "type": self.component_type,
            "name": self.component_name,
            "position": {"x": self.pos().x(), "y": self.pos().y()},
            "rotation": self.rotation(),
            "properties": {}
        }

    def display_current(self, current_value):
        self.hide_current_display()
        
        current_text = QGraphicsTextItem(self)
        current_text.setFont(RESULT_FONT)
        current_text.setDefaultTextColor(CURRENT_COLOR)
        current_text.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations)
        
        if isinstance(current_value, (int, float)):
            if abs(current_value) >= 1e-3:
                display_value = current_value * 1e3
                unit = "mA"
            elif abs(current_value) >= 1e-6:
                display_value = current_value * 1e6
                unit = "μA"
            else:
                display_value = current_value
                unit = "A"
            text = f"{display_value:.2f} {unit}"
        else:
            text = str(current_value)
            
        current_text.setPlainText(text)
        current_text.setPos(0, self.boundingRect().height() + 5)
        current_text.setZValue(RESULT_Z_VALUE)
        
        self.current_text_items.append(current_text)

    def hide_current_display(self):
        for item in self.current_text_items:
            if item.scene():
                item.scene().removeItem(item)
        self.current_text_items.clear()

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
                if new_capacitance > 0:
                    self.capacitance = new_capacitance
                    self.update_label_text()
                    return True
                else:
                    QMessageBox.warning(None, "Input Error", "Capacitance must be positive.")
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
            
            # Re-center label
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
