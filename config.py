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
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtCore import (Qt, QPointF, QRectF, QLineF, QByteArray, QDataStream,
                          QIODevice)

GRID_SIZE = 20
GRID_COLOR = QColor(220, 220, 220)
PIN_SIZE = 8
PIN_COLOR_DEFAULT = QColor(70, 140, 230)
PIN_COLOR_HOVER = QColor(255, 180, 0)
COMPONENT_Z_VALUE = 1
WIRE_Z_VALUE = 0
NODE_Z_VALUE = 2
JUNCTION_Z_VALUE = 2.5 # Slightly above nodes
LABEL_FONT = QFont("Segoe UI", 9)
WIRE_PEN = QPen(QColor(0, 120, 215), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
TEMP_WIRE_PEN = QPen(QColor(100, 180, 255), 2, Qt.PenStyle.DashLine)

NODE_LABEL_COLOR = QColor(50, 50, 50)
NODE_VOLTAGE_COLOR = QColor(0, 100, 0)
NODE_VOLTAGE_FONT = QFont("Segoe UI", 8)
GROUND_NODE_COLOR = QColor(200, 0, 0)

RESULT_FONT = QFont("Segoe UI", 8)
VOLTAGE_COLOR = QColor(0, 100, 0)
CURRENT_COLOR = QColor(150, 0, 0)
RESULT_Z_VALUE = 3

JUNCTION_SIZE = 6 # Size of the junction dot
JUNCTION_COLOR = QColor(0, 0, 0) # Black junction dot

RESISTOR_COLORS = {
    0: ("black", 1),
    1: ("brown", 10, 0.01),
    2: ("red", 100, 0.02),
    3: ("orange", 1000),
    4: ("yellow", 10000),
    5: ("green", 100000, 0.005),
    6: ("blue", 1000000, 0.0025),
    7: ("violet", 10000000, 0.001),
    8: ("grey", 100000000, 0.0005),
    9: ("white", 1000000000),
    -1: ("gold", 0.1, 0.05),
    -2: ("silver", 0.01, 0.10),
}

RESISTOR_VALUE_MAP = {
    0: "black", 1: "brown", 2: "red", 3: "orange", 4: "yellow",
    5: "green", 6: "blue", 7: "violet", 8: "grey", 9: "white"
}
RESISTOR_MULTIPLIER_MAP = {
    1: "black", 10: "brown", 100: "red", 1000: "orange", 10000: "yellow",
    100000: "green", 1000000: "blue", 10000000: "violet", 100000000: "grey",
    1000000000: "white", 0.1: "gold", 0.01: "silver"
}
RESISTOR_TOLERANCE_MAP = {
    0.01: "brown", 0.02: "red", 0.005: "green", 0.0025: "blue",
    0.001: "violet", 0.0005: "grey", 0.05: "gold", 0.10: "silver"
}

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
        # Removed self.value_text_item
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

    # Removed create_value_text and update_value_text_position methods


    def set_name(self, name):
        old_name = self.component_name
        self.component_name = name
        if self.label_item:
            self.update_label_text() # Use update_label_text to handle specific component formatting
            # Re-center label after text change
            label_rect = self.label_item.boundingRect()
            current_pos = self.label_item.pos()
            # Assuming label x_offset is relative to component center or left edge
            # This might need refinement based on component type
            x_offset_base = 0 # Default, adjust in subclasses if needed
            if hasattr(self, 'body_width'): x_offset_base = self.body_width / 2 # For components with a body
            elif hasattr(self, 'width'): x_offset_base = self.width / 2 # For components with a defined width

            new_x = x_offset_base - label_rect.width()/2 # Center relative to the component's local origin
            new_y = current_pos.y() # Keep the original y offset
            self.label_item.setPos(new_x, new_y)


        if hasattr(self.scene(), 'views') and self.scene().views():
             main_window = self.scene().views()[0].main_window
             if main_window:
                  main_window.deregister_component_name(self.component_type[0], old_name)
                  main_window.register_component_name(self.component_type[0], name)


    def itemChange(self, change, value):
        if change == QGraphicsItemGroup.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            if hasattr(self.scene(), 'views') and self.scene().views():
                 canvas = self.scene().views()[0]
                 if isinstance(canvas, CircuitCanvas) and canvas.snap_to_grid_enabled:
                      snapped_x = round(new_pos.x() / GRID_SIZE) * GRID_SIZE
                      snapped_y = round(new_pos.y() / GRID_SIZE) * GRID_SIZE
                      return QPointF(snapped_x, snapped_y)
            return new_pos

        if change == QGraphicsItemGroup.GraphicsItemChange.ItemPositionHasChanged:
             # Update connected wires when component moves
             for wire in self.connected_wires:
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
             wire.update_positions()
        if self.label_item:
             # Re-center label after rotation - Keep it centered relative to the component's local origin
             label_rect = self.label_item.boundingRect()
             # Assuming label x_offset was relative to component center or left edge
             x_offset_base = 0 # Default, adjust in subclasses if needed
             if hasattr(self, 'body_width'): x_offset_base = self.body_width / 2
             elif hasattr(self, 'width'): x_offset_base = self.width / 2

             # Calculate the new position relative to the rotated component's origin
             # This is a simplified approach and might need refinement for complex rotations
             # Keep the label centered horizontally relative to the component's local origin (0,0)
             new_x = 0 - label_rect.width()/2
             # Keep the label at its original vertical offset relative to the component's local origin
             # This assumes the original y_offset in create_label was relative to the component's origin
             # If it was relative to the bounding rect top, this might need adjustment
             new_y = self.label_item.pos().y() # Maintain original local y position

             self.label_item.setPos(new_x, new_y)


    def remove(self):
        print(f"Component.remove() called for {self.component_name}")
        scene = self.scene()
        if not scene:
            print("Component has no scene in remove(), cannot proceed.")
            return

        for wire in list(self.connected_wires):
            print(f"Removing connected wire: {wire}")
            wire.remove()

        if hasattr(scene, 'views') and scene.views():
             for view in scene.views():
                  if isinstance(view, CircuitCanvas):
                       if view.hovered_pin and view.hovered_pin not in self._pins:
                            pass
                       elif view.hovered_pin in self._pins:
                            view.hovered_pin = None
                            print(f"Cleared hovered pin reference for deleted component {self.component_name}")
        if isinstance(scene, QGraphicsScene):
             if hasattr(scene, 'views') and scene.views():
                 main_window = scene.views()[0].main_window
                 if main_window:
                     main_window.deregister_component_name(self.component_type[0], self.component_name)
                     if hasattr(main_window, 'netlist'):
                          print("Calling netlist.remove_component from Component.remove()")
                          main_window.netlist.remove_component(self)
                     else:
                          print("Could not access netlist from Component.remove()")
                 else:
                      print("Could not access main_window from Component.remove()")


        for item in self.current_text_items:
             if item.scene():
                  item.scene().removeItem(item)
        self.current_text_items.clear()

        # Removed value_text_item removal logic


        print(f"Removing component item from scene: {self}")
        scene.removeItem(self)
        print("Component item removed from scene.")
        print(f"Component.remove() finished for {self.component_name}.")


    def add_connected_wire(self, wire):
        if wire not in self.connected_wires:
            self.connected_wires.append(wire)

    def remove_connected_wire(self, wire):
        try:
            self.connected_wires.remove(wire)
            print(f"Removed wire {wire} from {self.component_name}'s connected_wires.")
        except ValueError:
            print(f"Wire {wire} not found in {self.component_name}'s connected_wires.")
            pass

    def get_properties(self):
        properties = {"Name": self.component_name}
        return properties

    def set_property(self, name, value):
        if name == "Name":
            self.set_name(str(value))
            return True
        return False

    def update_label_text(self):
        # Base implementation - subclasses should override
        if self.label_item:
            self.label_item.setPlainText(self.component_name)

    def to_dict(self):
        data = {
            "type": self.component_type,
            "name": self.component_name,
            "position": {"x": self.pos().x(), "y": self.pos().y()},
            "rotation": self.rotation(),
            "properties": {}
        }
        return data

    @staticmethod
    def from_dict(data, netlist):
        comp_type = data.get("type")
        name = data.get("name")
        pos_data = data.get("position", {"x": 0, "y": 0})
        position = QPointF(pos_data["x"], pos_data["y"])
        rotation = data.get("rotation", 0)
        properties = data.get("properties", {})

        component = None
        if comp_type == "Resistor":
            component = Resistor(name, position, properties.get("Resistance", 1000.0))
        elif comp_type == "VoltageSource":
            component = VoltageSource(name, position, properties.get("Voltage", 5.0))
        elif comp_type == "CurrentSource":
             component = CurrentSource(name, position, properties.get("Current", 1.0))
        elif comp_type == "Inductor":
             component = Inductor(name, position, properties.get("Inductance", 1e-3))
        elif comp_type == "Capacitor":
             component = Capacitor(name, position, properties.get("Capacitance", 1e-6))
        elif comp_type == "Ground":
             component = Ground(name, position)


        if component:
            component.setRotation(rotation)
            for prop_name, prop_value in properties.items():
                 if prop_name not in ["Resistance", "Voltage", "Current", "Inductance", "Capacitance", "Name"]:
                      component.set_property(prop_name, prop_value)

        return component

    def display_current(self, current_value):
        if not self.current_text_items:
             current_text = QGraphicsTextItem(self)
             current_text.setFont(RESULT_FONT)
             current_text.setDefaultTextColor(CURRENT_COLOR)
             current_text.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations)
             current_text.setZValue(RESULT_Z_VALUE)
             self.current_text_items.append(current_text)
        else:
             current_text = self.current_text_items[0]

        if isinstance(current_value, (int, float)):
             if abs(current_value) >= 1e-3:
                  display_value = current_value * 1e3
                  unit = "mA"
             elif abs(current_value) >= 1e-6:
                  display_value = current_value * 1e6
                  unit = "μA"
             elif abs(current_value) >= 1e-9:
                  display_value = current_value * 1e9
                  unit = "nA"
             else:
                  display_value = current_value
                  unit = "A"
             text = f"{display_value:.2f} {unit}"
        else:
             text = str(current_value)

        current_text.setPlainText(text)

        label_rect = self.label_item.boundingRect() if self.label_item else QRectF(0, 0, 0, 0)
        text_rect = current_text.boundingRect()

        # Position current text below the label, centered horizontally relative to the label's position
        text_x = self.label_item.pos().x() + label_rect.width()/2 - text_rect.width()/2 if self.label_item else self.boundingRect().center().x() - text_rect.width()/2
        text_y = (self.label_item.pos().y() + label_rect.height() + 5) if self.label_item else (self.boundingRect().bottom() + 5)
        current_text.setPos(text_x, text_y)


    def hide_current_display(self):
        for item in self.current_text_items:
             if item.scene():
                  item.scene().removeItem(item)
        self.current_text_items.clear()
