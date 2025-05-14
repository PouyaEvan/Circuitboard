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
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF

from config import *
from components.wire import Wire
from components.capacitor import Capacitor, Component
from components.ground import Ground
from components.inductor import Inductor
from components.resistor import Resistor
from components.vs import VoltageSource
from components.cs import CurrentSource

class CircuitCanvas(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.main_window = parent
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(QBrush(Qt.GlobalColor.white))
        self.current_tool = None
        self.start_pin_item = None
        self.temp_wire_path_item = None
        self.setMouseTracking(True)
        self.hovered_pin = None
        self.snap_to_grid_enabled = True # Added snap-to-grid toggle

        self._pan_start_pos = QPointF()
        self._panning = False

        self.scene().selectionChanged.connect(self.on_selection_changed) # Connect selection change signal

    def set_tool(self, tool_name):
        self.current_tool = tool_name
        print(f"Tool selected: {self.current_tool}")
        if tool_name == 'wire':
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif tool_name is None:
             self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
             self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
             self.setDragMode(QGraphicsView.DragMode.NoDrag)
             self.setCursor(Qt.CursorShape.CrossCursor)

        self.start_pin_item = None
        if self.temp_wire_path_item and self.scene():
             self.scene().removeItem(self.temp_wire_path_item)
        self.temp_wire_path_item = None


    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if self.snap_to_grid_enabled: # Only draw grid if enabled
            left = int(rect.left()) - int(rect.left()) % GRID_SIZE
            top = int(rect.top()) - int(rect.top()) % GRID_SIZE
            lines = []
            x = left
            while x < rect.right(): lines.append(QLineF(x, rect.top(), x, rect.bottom())); x += GRID_SIZE
            y = top
            while y < rect.bottom(): lines.append(QLineF(rect.left(), y, rect.right(), y)); y += GRID_SIZE
            pen = QPen(GRID_COLOR, 1, Qt.PenStyle.DotLine); painter.setPen(pen); painter.drawLines(lines)


    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        items_at_pos = self.items(event.pos())
        pin_item = self.find_pin_at(items_at_pos)

        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_tool == 'resistor':
                name = self.main_window.get_next_component_name("R")
                resistor = Resistor(name, self.snap_to_grid(scene_pos) if self.snap_to_grid_enabled else scene_pos) # Apply snap based on toggle
                self.scene().addItem(resistor)
                self.main_window.netlist.add_component(resistor)
                self.set_tool(None)
            elif self.current_tool == 'voltage':
                name = self.main_window.get_next_component_name("V")
                source = VoltageSource(name, self.snap_to_grid(scene_pos) if self.snap_to_grid_enabled else scene_pos) # Apply snap based on toggle
                self.scene().addItem(source)
                self.main_window.netlist.add_component(source)
                self.set_tool(None)
            elif self.current_tool == 'currentsource':
                 name = self.main_window.get_next_component_name("I")
                 source = CurrentSource(name, self.snap_to_grid(scene_pos) if self.snap_to_grid_enabled else scene_pos) # Apply snap based on toggle
                 self.scene().addItem(source)
                 self.main_window.netlist.add_component(source)
                 self.set_tool(None)
            elif self.current_tool == 'inductor':
                 name = self.main_window.get_next_component_name("L")
                 inductor = Inductor(name, self.snap_to_grid(scene_pos) if self.snap_to_grid_enabled else scene_pos) # Apply snap based on toggle
                 self.scene().addItem(inductor)
                 self.main_window.netlist.add_component(inductor)
                 self.set_tool(None)
            elif self.current_tool == 'ground':
                 name = self.main_window.get_next_component_name("GND")
                 ground = Ground(name, self.snap_to_grid(scene_pos) if self.snap_to_grid_enabled else scene_pos) # Apply snap based on toggle
                 self.scene().addItem(ground)
                 self.main_window.netlist.add_component(ground)
                 self.set_tool(None)
            elif self.current_tool == 'capacitor':
                 name = self.main_window.get_next_component_name("C")
                 capacitor = Capacitor(name, self.snap_to_grid(scene_pos) if self.snap_to_grid_enabled else scene_pos) # Apply snap based on toggle
                 self.scene().addItem(capacitor)
                 self.main_window.netlist.add_component(capacitor)
                 self.set_tool(None)
            elif self.current_tool == 'wire':
                if pin_item:
                    self.start_pin_item = pin_item
                    start_pos = self.start_pin_item.scenePos()
                    self.temp_wire_path_item = QGraphicsPathItem()
                    self.temp_wire_path_item.setPen(TEMP_WIRE_PEN)
                    self.temp_wire_path_item.setZValue(WIRE_Z_VALUE + 0.1)
                    self.scene().addItem(self.temp_wire_path_item)
                    print(f"Started wire from pin: {pin_item.data(1)} on {pin_item.data(2).component_name}")
                else:
                    print("Click on a component pin to start drawing a wire.")

            else:
                super().mousePressEvent(event)

        elif event.button() == Qt.MouseButton.RightButton:
             component = self.find_component_at(items_at_pos)
             node_visual = self.find_node_visual_at(items_at_pos)
             if component:
                 self.show_component_context_menu(component, event.globalPosition().toPoint())
             elif node_visual:
                  self.show_node_context_menu(node_visual, event.globalPosition().toPoint())
             else:
                 super().mousePressEvent(event)

        elif event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start_pos = event.pos()
            self._panning = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        items_at_pos = self.items(event.pos())
        pin_item = self.find_pin_at(items_at_pos)

        if self._panning:
            delta = self.mapToScene(event.pos()) - self.mapToScene(self._pan_start_pos)
            self.translate(delta.x(), delta.y())
            self._pan_start_pos = event.pos()
            event.accept()
            return

        if self.current_tool == 'wire' and self.start_pin_item and self.temp_wire_path_item:
             start_pos = self.start_pin_item.scenePos()
             # Snap end position to grid if enabled, unless hovering over a pin
             end_pos = pin_item.scenePos() if pin_item else (self.snap_to_grid(scene_pos) if self.snap_to_grid_enabled else scene_pos)

             temp_points = self.generate_orthogonal_points_preview(start_pos, end_pos)

             path = QPainterPath()
             if temp_points:
                 path.moveTo(temp_points[0])
                 for i in range(1, len(temp_points)):
                     path.lineTo(temp_points[i])
             self.temp_wire_path_item.setPath(path)


        if self.current_tool in ['wire', None]:
            if self.hovered_pin and self.hovered_pin not in self.scene().items():
                 self.hovered_pin = None

            if pin_item and pin_item != self.hovered_pin:
                if self.hovered_pin: self.hovered_pin.setBrush(QBrush(PIN_COLOR_DEFAULT))
                self.hovered_pin = pin_item
                self.hovered_pin.setBrush(QBrush(PIN_COLOR_HOVER))
            elif not pin_item and self.hovered_pin:
                self.hovered_pin.setBrush(QBrush(PIN_COLOR_DEFAULT))
                self.hovered_pin = None

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_tool == 'wire' and self.start_pin_item and self.temp_wire_path_item:
                scene_pos = self.mapToScene(event.pos())
                # Use a small radius to find nearby pins for connection
                detection_radius = PIN_SIZE * 1.5 # Adjust radius as needed
                # Create a QRectF for the detection area
                detection_rect = QRectF(scene_pos.x() - detection_radius, scene_pos.y() - detection_radius,
                                        detection_radius * 2, detection_radius * 2)
                nearby_items = self.scene().items(detection_rect, Qt.ItemSelectionMode.IntersectsItemShape)

                end_pin_item = self.find_pin_at(nearby_items)


                if self.temp_wire_path_item and self.temp_wire_path_item.scene():
                     self.scene().removeItem(self.temp_wire_path_item)
                self.temp_wire_path_item = None

                if end_pin_item and end_pin_item != self.start_pin_item:
                    if end_pin_item.data(2) != self.start_pin_item.data(2) or end_pin_item != self.start_pin_item:
                         try:
                             start_pos = self.start_pin_item.scenePos()
                             end_pos = end_pin_item.scenePos()
                             wire_points = self.generate_orthogonal_points(start_pos, end_pos)

                             wire = Wire(self.start_pin_item, end_pin_item)
                             self.scene().addItem(wire)
                             self.main_window.netlist.add_wire(wire) # This handles node merging/creation
                             wire.update_positions()

                             print(f"Wire added between {self.start_pin_item.data(2).component_name} pin {self.start_pin_item.data(1)} and {end_pin_item.data(2).component_name} pin {end_pin_item.data(1)}.")
                         except ValueError as e: print(f"Error creating wire: {e}")
                    else:
                         print("Wire cancelled: Cannot connect a pin to itself or another pin on the same component (currently unsupported).")

                else:
                    print("Wire cancelled: End point not on a valid pin or same as start pin.")

                self.start_pin_item = None

            else:
                selected_items = self.scene().selectedItems()
                moved_components = [item for item in selected_items if isinstance(item, Component)]

                super().mouseReleaseEvent(event)

                wires_to_update = set()
                for comp in moved_components:
                    for wire in comp.connected_wires:
                         wires_to_update.add(wire)

                for wire in wires_to_update:
                    if wire.scene():
                        wire.update_positions()

                self.update_node_visuals()

                if moved_components and hasattr(self.main_window, 'hide_simulation_results'):
                     self.main_window.hide_simulation_results()


        elif event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start_pos = event.pos()
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()

        else:
             super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return

        zoom_factor = 1.15
        if delta < 0:
            zoom_factor = 1.0 / zoom_factor

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(zoom_factor, zoom_factor)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)


    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            selected_items = self.scene().selectedItems()
            print(f"Delete key pressed. Number of selected items: {len(selected_items)}")
            if not selected_items:
                print("No items selected for deletion.")
                return

            print(f"Deleting {len(selected_items)} selected item(s)...")
            for item in list(selected_items):
                print(f"Processing item for deletion: {item}, type: {type(item)}, scene: {item.scene()}")
                if item and item.scene():
                    if isinstance(item, Component):
                        print(f"Item is a Component: {item.component_name}. Calling remove().")
                        item.remove()
                    elif isinstance(item, Wire):
                        print(f"Item is a Wire: {item}. Calling remove().")
                        item.remove()
                    else:
                        print(f"Item is not a Component or Wire. Removing directly from scene: {item}")
                        if item.scene():
                            item.scene().removeItem(item)
                        else:
                            print("Item has no scene, cannot remove directly.")
                else:
                     print(f"Skipping removal of item {item} as it has no scene.")

            print("Deletion process finished.")

        elif event.matches(QKeySequence.StandardKey.Copy): # Handle Copy
             self.main_window.copy_selected_items()
             event.accept()

        elif event.matches(QKeySequence.StandardKey.Paste): # Handle Paste
             self.main_window.paste_items()
             event.accept()


        elif event.key() == Qt.Key.Key_Escape:
             select_action = self.main_window.findChild(QAction, "select_action")
             if select_action:
                 self.main_window.activate_tool(select_action, None)
             else:
                 print("Warning: Select action not found.")

        else:
            super().keyPressEvent(event)

    def snap_to_grid(self, pos):
        return QPointF(round(pos.x() / GRID_SIZE) * GRID_SIZE, round(pos.y() / GRID_SIZE) * GRID_SIZE)

    def find_pin_at(self, items_list):
        for item in items_list:
            if isinstance(item, QGraphicsEllipseItem) and item.data(0) == "pin":
                return item
            current = item
            while current.parentItem():
                 current = current.parentItem()
                 if isinstance(current, QGraphicsEllipseItem) and current.data(0) == "pin":
                     return current
        return None

    def find_component_at(self, items_list):
        for item in items_list:
            if isinstance(item, Component): return item
            current = item
            while current.parentItem():
                 current = current.parentItem()
                 if isinstance(current, Component): return current
        return None

    def find_node_visual_at(self, items_list):
        """Finds the node visual group item at the given position."""
        for item in items_list:
             if isinstance(item, QGraphicsItemGroup) and item in self.main_window.netlist.node_visuals.values():
                  return item
             current = item
             while current.parentItem():
                  current = current.parentItem()
                  if isinstance(current, QGraphicsItemGroup) and current in self.main_window.netlist.node_visuals.values():
                       return current
        return None

    def on_selection_changed(self):
        """Updates the properties panel when the selection changes."""
        selected_items = self.scene().selectedItems()
        self.main_window.properties_panel.update_properties_display(selected_items)


    def show_component_context_menu(self, component, global_pos):
        menu = QMenu(self)

        rotate_action = QAction("Rotate 90°", self)
        rotate_action.triggered.connect(lambda: self.rotate_component(component))

        rename_action = QAction("Rename...", self)
        rename_action.triggered.connect(lambda: self.rename_component(component))

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_component(component))

        menu.addAction(rotate_action)
        menu.addAction(rename_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def show_node_context_menu(self, node_visual_item, global_pos):
        """Shows a context menu for a node visual item."""
        menu = QMenu(self)

        node = None
        for n, visual in self.main_window.netlist.node_visuals.items():
             if visual == node_visual_item:
                  node = n
                  break

        if node:
             set_ground_action = QAction(f"Set Node {node.node_id} as Ground", self)
             set_ground_action.triggered.connect(lambda: self.main_window.netlist.set_ground_node(node.node_id))
             menu.addAction(set_ground_action)

             if node.is_ground:
                  clear_ground_action = QAction(f"Clear Node {node.node_id} as Ground", self)
                  clear_ground_action.triggered.connect(lambda: self.main_window.netlist.set_ground_node(None))
                  menu.addAction(clear_ground_action)


        menu.exec(global_pos)


    def rotate_component(self, component):
        if component:
            component.rotate(90)
            wires_to_update = set(component.connected_wires)
            for wire in wires_to_update:
                 if wire.scene(): wire.update_positions()

            self.update_node_visuals()

            if hasattr(self.main_window, 'hide_simulation_results'):
                 self.main_window.hide_simulation_results()


    def rename_component(self, component):
        if not component: return
        current_name = component.component_name
        new_name, ok = QInputDialog.getText(self, "Rename Component", "Enter new name:", text=current_name)
        if ok and new_name and new_name != current_name:
            is_unique = True
            for item in self.scene().items():
                if isinstance(item, Component) and item != component and item.component_name == new_name:
                    is_unique = False
                    QMessageBox.warning(self, "Rename Error", f"Name '{new_name}' is already taken.")
                    break
            if is_unique:
                component.set_name(new_name) # set_name now handles deregister/register
                if hasattr(self.main_window, 'hide_simulation_results'):
                     self.main_window.hide_simulation_results()
                self.main_window.properties_panel.update_properties_display(self.scene().selectedItems()) # Update panel


    def edit_component_properties(self, component):
        # This method is now replaced by the PropertiesPanel
        pass

    def delete_component(self, component):
        if component and component.scene():
            print(f"Deleting {component.component_name} via context menu.")
            component.remove()


    def generate_orthogonal_points_preview(self, start_pos, end_pos):
        """Generates orthogonal points for the temporary wire preview."""
        points = [start_pos]

        # Use snapped positions for routing if snap is enabled
        route_start_pos = self.snap_to_grid(start_pos) if self.snap_to_grid_enabled else start_pos
        route_end_pos = self.snap_to_grid(end_pos) if self.snap_to_grid_enabled else end_pos

        dx = route_end_pos.x() - route_start_pos.x()
        dy = route_end_pos.y() - route_start_pos.y()

        # Determine the intermediate point for a single bend
        # Prioritize horizontal then vertical if dx is larger, otherwise vertical then horizontal
        if abs(dx) > abs(dy):
            intermediate_point = QPointF(route_end_pos.x(), route_start_pos.y())
        else:
            intermediate_point = QPointF(route_start_pos.x(), route_end_pos.y())

        points.append(intermediate_point)
        points.append(end_pos)

        return points


    def generate_orthogonal_points(self, start_pos, end_pos):
        """Generates orthogonal points for a permanent wire."""
        # For now, use the same logic as preview for simplicity (single bend)
        # More advanced routing could be implemented here later
        return self.generate_orthogonal_points_preview(start_pos, end_pos)

    def update_node_visuals(self):
        scene = self.scene()
        if not scene: return

        for node, node_group in list(self.main_window.netlist.node_visuals.items()):
            if node_group.scene():
                if node.voltage_text_item and node.voltage_text_item.scene():
                     scene.removeItem(node.voltage_text_item)
                     node.voltage_text_item = None
                if node.junction_item and node.junction_item.scene(): # Remove old junction
                     scene.removeItem(node.junction_item)
                     node.junction_item = None
                scene.removeItem(node_group)
        self.main_window.netlist.node_visuals.clear()
        self.main_window.netlist.junction_visuals.clear() # Clear junction visuals dict

        for node_id, node in self.main_window.netlist.nodes.items():
            if node.connected_pins:
                # Calculate average position based on connected pins
                avg_x = sum(pin_item.scenePos().x() for comp, pin_name, pin_item in node.connected_pins) / len(node.connected_pins)
                avg_y = sum(pin_item.scenePos().y() for comp, pin_name, pin_item in node.connected_pins) / len(node.connected_pins)
                representative_pos = QPointF(avg_x, avg_y)

                # If snap to grid is enabled, snap the node visual position
                snapped_pos = self.snap_to_grid(representative_pos) if self.snap_to_grid_enabled else representative_pos

                node_group = QGraphicsItemGroup()
                node_group.setPos(snapped_pos)
                node_group.setZValue(NODE_Z_VALUE)

                node_label_text = str(node_id)
                if node.is_ground:
                     node_label_text += " (GND)"

                node_label = QGraphicsTextItem(node_label_text, node_group)
                node_label.setFont(LABEL_FONT)
                node_label.setDefaultTextColor(GROUND_NODE_COLOR if node.is_ground else NODE_LABEL_COLOR)
                # Position the label relative to the node group's origin
                label_offset_x = 10
                label_offset_y = -20
                node_label.setPos(label_offset_x, label_offset_y)
                node_label.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations)

                scene.addItem(node_group)
                self.main_window.netlist.node_visuals[node] = node_group

                voltage_text_item = QGraphicsTextItem(node_group)
                scene.addItem(voltage_text_item)
                voltage_text_item.setFont(NODE_VOLTAGE_FONT)
                voltage_text_item.setDefaultTextColor(NODE_VOLTAGE_COLOR)
                # Position voltage text below the node label
                voltage_text_item.setPos(label_offset_x, label_offset_y + node_label.boundingRect().height() + 2)
                voltage_text_item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations)
                voltage_text_item.setZValue(RESULT_Z_VALUE)
                voltage_text_item.setVisible(False)
                node.voltage_text_item = voltage_text_item

                # Add junction dot if more than 2 connections
                if len(node.connected_pins) > 2:
                     junction_item = QGraphicsEllipseItem(-JUNCTION_SIZE/2, -JUNCTION_SIZE/2, JUNCTION_SIZE, JUNCTION_SIZE, node_group)
                     junction_item.setBrush(QBrush(JUNCTION_COLOR))
                     # Corrected typo: Qt.NoPen -> Qt.PenStyle.NoPen
                     junction_item.setPen(QPen(Qt.PenStyle.NoPen))
                     junction_item.setPos(0, 0) # Position at the node group origin
                     junction_item.setZValue(JUNCTION_Z_VALUE)
                     node.junction_item = junction_item
                     self.main_window.netlist.junction_visuals[node] = junction_item
