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

# Try to import advanced wire system
try:
    from components.advanced_wire import AdvancedWire, WireType, WireStyle
    ADVANCED_WIRE_AVAILABLE = True
except ImportError:
    ADVANCED_WIRE_AVAILABLE = False


class Wire(QGraphicsPathItem):
    def __init__(self, start_pin, end_pin, parent=None):
        super().__init__(parent)
        
        # Try to use advanced wire if available
        if ADVANCED_WIRE_AVAILABLE:
            try:
                # Create advanced wire instance
                self._advanced_wire = AdvancedWire(start_pin, end_pin, WireType.NORMAL, parent)
                self._using_advanced = True
                
                # Delegate core properties
                self.start_pin = self._advanced_wire.start_pin
                self.end_pin = self._advanced_wire.end_pin
                self.start_comp = self._advanced_wire.start_comp
                self.end_comp = self._advanced_wire.end_comp
                self._points = self._advanced_wire._points
                
                # Copy visual properties
                self.setPen(self._advanced_wire.pen())
                self.setZValue(self._advanced_wire.zValue())
                self.setFlags(self._advanced_wire.flags())
                self.setPath(self._advanced_wire.path())
                
                print("Advanced wire system initialized successfully.")
                return
                
            except Exception as e:
                print(f"Failed to initialize advanced wire: {e}")
                print("Falling back to legacy wire...")
        
        # Legacy initialization
        self._using_advanced = False
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
        # Delegate to advanced wire if available
        if self._using_advanced:
            self._advanced_wire.update_positions()
            # Sync visual properties
            self.setPath(self._advanced_wire.path())
            return
        
        # Legacy implementation
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
        # Delegate to advanced wire if available
        if self._using_advanced:
            return self._advanced_wire.remove()
        
        # Legacy implementation
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

    def show_current_arrow(self, current_value, direction):
        # Delegate to advanced wire if available
        if self._using_advanced:
            return self._advanced_wire.show_current_arrow(current_value, direction)
        
        # Legacy implementation
        # Remove any existing arrow
        if hasattr(self, '_current_arrow') and self._current_arrow:
            scene = self.scene()
            if scene and self._current_arrow.scene():
                scene.removeItem(self._current_arrow)
            self._current_arrow = None
        if abs(current_value) < 1e-12:
            return  # Don't show arrow for zero current
        # Draw a filled triangle arrow in the middle of the wire
        if self._points and len(self._points) >= 2:
            mid_idx = len(self._points) // 2
            p1 = self._points[mid_idx - 1]
            p2 = self._points[mid_idx]
            # Arrow direction: → for direction==1, ← for direction==-1
            if direction == 0:
                return
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            length = (dx**2 + dy**2) ** 0.5
            if length == 0:
                return
            ux, uy = dx / length, dy / length
            if direction == -1:
                ux, uy = -ux, -uy
            arrow_len = 18
            arrow_w = 8
            xm = (p1.x() + p2.x()) / 2
            ym = (p1.y() + p2.y()) / 2
            # Arrow tip
            x_tip = xm + ux * arrow_len / 2
            y_tip = ym + uy * arrow_len / 2
            # Arrow base center
            x_base = xm - ux * arrow_len / 2
            y_base = ym - uy * arrow_len / 2
            # Perpendicular vector for width
            perp_ux, perp_uy = -uy, ux
            # Triangle points
            left_x = x_base + perp_ux * arrow_w / 2
            left_y = y_base + perp_uy * arrow_w / 2
            right_x = x_base - perp_ux * arrow_w / 2
            right_y = y_base - perp_uy * arrow_w / 2
            from PyQt6.QtWidgets import QGraphicsPolygonItem
            from PyQt6.QtGui import QPolygonF, QBrush
            from PyQt6.QtCore import QPointF
            triangle = QPolygonF([
                QPointF(x_tip, y_tip),
                QPointF(left_x, left_y),
                QPointF(right_x, right_y)
            ])
            arrow_item = QGraphicsPolygonItem(triangle, self)
            arrow_item.setBrush(QBrush(QColor(200, 0, 0)))
            arrow_item.setPen(QPen(QColor(200, 0, 0), 1))
            arrow_item.setZValue(self.zValue() + 0.2)
            self._current_arrow = arrow_item

    def update_current_visual(self, current_value, direction):
        # Delegate to advanced wire if available
        if self._using_advanced:
            return self._advanced_wire.update_current_visual(current_value, direction)
        
        # Legacy implementation
        self.show_current_arrow(current_value, direction)
        # Show current value as text (absolute value)
        if hasattr(self, '_current_text') and self._current_text:
            scene = self.scene()
            if scene and self._current_text.scene():
                scene.removeItem(self._current_text)
            self._current_text = None
        if abs(current_value) < 1e-12:
            return
        from PyQt6.QtWidgets import QGraphicsTextItem
        abs_value = abs(current_value)
        if abs_value >= 1e-3:
            display_value = abs_value * 1e3
            unit = "mA"
        elif abs_value >= 1e-6:
            display_value = abs_value * 1e6
            unit = "μA"
        elif abs_value >= 1e-9:
            display_value = abs_value * 1e9
            unit = "nA"
        else:
            display_value = abs_value
            unit = "A"
        arrow = "→" if direction == 1 else ("←" if direction == -1 else "-")
        text = f"{display_value:.2f} {unit} {arrow}"
        mid_idx = len(self._points) // 2
        xm = (self._points[mid_idx - 1].x() + self._points[mid_idx].x()) / 2
        ym = (self._points[mid_idx - 1].y() + self._points[mid_idx].y()) / 2
        text_item = QGraphicsTextItem(text, self)
        text_item.setFont(QFont("Segoe UI", 8))
        text_item.setDefaultTextColor(QColor(200, 0, 0))
        text_item.setZValue(self.zValue() + 0.3)
        text_item.setPos(xm, ym)
        self._current_text = text_item

    def hide_current_display(self):
        """Hide current arrows and text from the wire."""
        # Delegate to advanced wire if available
        if self._using_advanced:
            return self._advanced_wire.hide_current_display()
        
        # Legacy implementation
        # Remove current arrow
        if hasattr(self, '_current_arrow') and self._current_arrow:
            scene = self.scene()
            if scene and self._current_arrow.scene():
                scene.removeItem(self._current_arrow)
            self._current_arrow = None
        
        # Remove current text
        if hasattr(self, '_current_text') and self._current_text:
            scene = self.scene()
            if scene and self._current_text.scene():
                scene.removeItem(self._current_text)
            self._current_text = None

