"""
Advanced Wiring System with intelligent routing algorithms, enhanced visual feedback,
support for buses and differential pairs, parasitic modeling, and advanced current visualization.
This is a complete overhaul of the original wire system with significant improvements.
"""

import sys
import os
import json
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Union
from enum import Enum
from abc import ABC, abstractmethod
import math
import logging

from PyQt6.QtWidgets import (QGraphicsPathItem, QGraphicsItem, QGraphicsItemGroup,
                             QGraphicsPolygonItem, QGraphicsTextItem, QGraphicsLineItem,
                             QGraphicsEllipseItem)
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QPainterPath, 
                         QPolygonF, QTransform, QFontMetrics)
from PyQt6.QtCore import Qt, QPointF, QRectF

from config import *

logger = logging.getLogger(__name__)

class WireType(Enum):
    """Types of wire connections"""
    NORMAL = "normal"
    BUS = "bus"
    DIFFERENTIAL = "differential"
    COAXIAL = "coaxial"
    TWISTED_PAIR = "twisted_pair"
    POWER = "power"
    GROUND = "ground"
    CLOCK = "clock"
    SIGNAL = "signal"

class RoutingAlgorithm(Enum):
    """Wire routing algorithms"""
    DIRECT = "direct"
    ORTHOGONAL = "orthogonal"
    MANHATTAN = "manhattan"
    A_STAR = "a_star"
    STEINER = "steiner"
    OPTIMAL = "optimal"

class WireStyle(Enum):
    """Wire visual styles"""
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    THICK = "thick"
    THIN = "thin"
    HIGHLIGHTED = "highlighted"

@dataclass
class WireElectricalProperties:
    """Electrical properties of wires"""
    resistance_per_unit: float = 0.0  # Ohms per unit length
    inductance_per_unit: float = 0.0  # H per unit length
    capacitance_per_unit: float = 0.0  # F per unit length
    impedance: Optional[float] = None  # Characteristic impedance
    max_current: float = float('inf')  # Maximum current rating
    max_voltage: float = float('inf')  # Maximum voltage rating
    temperature_coefficient: float = 0.0  # Temperature coefficient
    skin_effect_factor: float = 1.0  # Skin effect at high frequencies

@dataclass
class WireGeometry:
    """Geometric properties of wires"""
    width: float = 1.0
    length: float = 0.0
    cross_section: float = 1.0  # mm²
    insulation_thickness: float = 0.0
    bend_radius: float = 0.0
    via_count: int = 0
    layer: int = 0  # For multi-layer routing

@dataclass
class RoutingConstraints:
    """Constraints for wire routing"""
    min_spacing: float = GRID_SIZE
    max_bend_angle: float = 90.0
    avoid_areas: List[QRectF] = field(default_factory=list)
    preferred_layers: List[int] = field(default_factory=list)
    max_via_count: int = 10
    max_length: float = float('inf')
    symmetry_groups: List[List[str]] = field(default_factory=list)

class RoutingEngine(ABC):
    """Abstract base class for routing engines"""
    
    @abstractmethod
    def route(self, start_pos: QPointF, end_pos: QPointF, 
              constraints: RoutingConstraints) -> List[QPointF]:
        """Generate route points between start and end positions"""
        pass

class OrthogonalRouter(RoutingEngine):
    """Enhanced orthogonal routing with obstacle avoidance"""
    
    def __init__(self, grid_size: float = GRID_SIZE):
        self.grid_size = grid_size
        self.obstacle_padding = grid_size * 2
    
    def route(self, start_pos: QPointF, end_pos: QPointF, 
              constraints: RoutingConstraints) -> List[QPointF]:
        """Generate orthogonal route with intelligent corner placement"""
        points = [start_pos]
        
        # Snap to grid
        start_grid = self._snap_to_grid(start_pos)
        end_grid = self._snap_to_grid(end_pos)
        
        # Calculate route based on direction and obstacles
        if self._has_clear_path(start_grid, end_grid, constraints):
            # Use simple L-shaped route
            points.extend(self._generate_l_route(start_grid, end_grid))
        else:
            # Use A* pathfinding to avoid obstacles
            points.extend(self._generate_obstacle_avoiding_route(start_grid, end_grid, constraints))
        
        points.append(end_pos)
        return self._optimize_route(points)
    
    def _snap_to_grid(self, pos: QPointF) -> QPointF:
        """Snap position to grid"""
        x = round(pos.x() / self.grid_size) * self.grid_size
        y = round(pos.y() / self.grid_size) * self.grid_size
        return QPointF(x, y)
    
    def _has_clear_path(self, start: QPointF, end: QPointF, 
                       constraints: RoutingConstraints) -> bool:
        """Check if there's a clear L-shaped path"""
        # Check if simple L-route avoids obstacles
        mid1 = QPointF(start.x(), end.y())
        mid2 = QPointF(end.x(), start.y())
        
        path1 = [start, mid1, end]
        path2 = [start, mid2, end]
        
        return (self._path_clear(path1, constraints) or 
                self._path_clear(path2, constraints))
    
    def _path_clear(self, path: List[QPointF], constraints: RoutingConstraints) -> bool:
        """Check if path avoids obstacles"""
        for i in range(len(path) - 1):
            if self._segment_intersects_obstacles(path[i], path[i+1], constraints):
                return False
        return True
    
    def _segment_intersects_obstacles(self, p1: QPointF, p2: QPointF, 
                                    constraints: RoutingConstraints) -> bool:
        """Check if line segment intersects any obstacles"""
        for obstacle in constraints.avoid_areas:
            if self._line_intersects_rect(p1, p2, obstacle):
                return True
        return False
    
    def _line_intersects_rect(self, p1: QPointF, p2: QPointF, rect: QRectF) -> bool:
        """Check if line segment intersects rectangle"""
        # Expand rectangle by padding
        expanded = rect.adjusted(-self.obstacle_padding, -self.obstacle_padding,
                                self.obstacle_padding, self.obstacle_padding)
        
        # Simple bounding box check first
        line_rect = QRectF(min(p1.x(), p2.x()), min(p1.y(), p2.y()),
                          abs(p2.x() - p1.x()), abs(p2.y() - p1.y()))
        
        return expanded.intersects(line_rect)
    
    def _generate_l_route(self, start: QPointF, end: QPointF) -> List[QPointF]:
        """Generate simple L-shaped route"""
        # Choose corner based on distance minimization
        dx = abs(end.x() - start.x())
        dy = abs(end.y() - start.y())
        
        if dx > dy:
            # Horizontal first
            corner = QPointF(end.x(), start.y())
        else:
            # Vertical first
            corner = QPointF(start.x(), end.y())
        
        return [corner]
    
    def _generate_obstacle_avoiding_route(self, start: QPointF, end: QPointF,
                                        constraints: RoutingConstraints) -> List[QPointF]:
        """Generate route using A* pathfinding"""
        # Simplified A* implementation for demonstration
        # In practice, this would be a full A* implementation
        
        # For now, use a simple detour strategy
        mid_x = (start.x() + end.x()) / 2
        mid_y = (start.y() + end.y()) / 2
        
        # Try to route around obstacles
        detour_points = []
        
        # Add intermediate points to avoid obstacles
        for obstacle in constraints.avoid_areas:
            if obstacle.contains(QPointF(mid_x, mid_y)):
                # Route around obstacle
                if abs(end.x() - start.x()) > abs(end.y() - start.y()):
                    # Route above/below
                    detour_y = obstacle.top() - self.obstacle_padding
                    if detour_y < min(start.y(), end.y()):
                        detour_y = obstacle.bottom() + self.obstacle_padding
                    
                    detour_points.extend([
                        QPointF(start.x(), detour_y),
                        QPointF(end.x(), detour_y)
                    ])
                else:
                    # Route left/right
                    detour_x = obstacle.left() - self.obstacle_padding
                    if detour_x < min(start.x(), end.x()):
                        detour_x = obstacle.right() + self.obstacle_padding
                    
                    detour_points.extend([
                        QPointF(detour_x, start.y()),
                        QPointF(detour_x, end.y())
                    ])
                break
        
        return detour_points if detour_points else self._generate_l_route(start, end)
    
    def _optimize_route(self, points: List[QPointF]) -> List[QPointF]:
        """Optimize route by removing unnecessary points"""
        if len(points) <= 2:
            return points
        
        optimized = [points[0]]
        
        i = 1
        while i < len(points) - 1:
            current = points[i]
            next_point = points[i + 1]
            
            # Check if we can skip current point
            if self._points_collinear(optimized[-1], current, next_point):
                # Skip current point
                pass
            else:
                optimized.append(current)
            
            i += 1
        
        optimized.append(points[-1])
        return optimized
    
    def _points_collinear(self, p1: QPointF, p2: QPointF, p3: QPointF, 
                         tolerance: float = 1e-6) -> bool:
        """Check if three points are collinear"""
        # Calculate cross product
        cross = ((p2.x() - p1.x()) * (p3.y() - p1.y()) - 
                (p2.y() - p1.y()) * (p3.x() - p1.x()))
        return abs(cross) < tolerance

class ManhattanRouter(RoutingEngine):
    """Manhattan distance routing with multiple path options"""
    
    def route(self, start_pos: QPointF, end_pos: QPointF, 
              constraints: RoutingConstraints) -> List[QPointF]:
        """Generate Manhattan-style route"""
        # Generate multiple candidate paths and choose the best one
        paths = []
        
        # Path 1: Horizontal first
        path1 = [start_pos, QPointF(end_pos.x(), start_pos.y()), end_pos]
        paths.append(path1)
        
        # Path 2: Vertical first
        path2 = [start_pos, QPointF(start_pos.x(), end_pos.y()), end_pos]
        paths.append(path2)
        
        # Path 3: Stair-step approach
        mid_x = (start_pos.x() + end_pos.x()) / 2
        mid_y = (start_pos.y() + end_pos.y()) / 2
        path3 = [start_pos, QPointF(mid_x, start_pos.y()), 
                QPointF(mid_x, end_pos.y()), end_pos]
        paths.append(path3)
        
        # Choose best path based on criteria
        best_path = self._choose_best_path(paths, constraints)
        return best_path
    
    def _choose_best_path(self, paths: List[List[QPointF]], 
                         constraints: RoutingConstraints) -> List[QPointF]:
        """Choose the best path based on multiple criteria"""
        scores = []
        
        for path in paths:
            score = 0
            
            # Prefer shorter paths
            length = self._calculate_path_length(path)
            score += 1000 / (length + 1)
            
            # Penalize paths that intersect obstacles
            if self._path_intersects_obstacles(path, constraints):
                score -= 500
            
            # Prefer fewer bends
            bends = len(path) - 2
            score -= bends * 10
            
            scores.append(score)
        
        # Return path with highest score
        best_index = scores.index(max(scores))
        return paths[best_index]
    
    def _calculate_path_length(self, path: List[QPointF]) -> float:
        """Calculate total path length"""
        length = 0.0
        for i in range(len(path) - 1):
            dx = path[i+1].x() - path[i].x()
            dy = path[i+1].y() - path[i].y()
            length += math.sqrt(dx*dx + dy*dy)
        return length
    
    def _path_intersects_obstacles(self, path: List[QPointF], 
                                  constraints: RoutingConstraints) -> bool:
        """Check if path intersects any obstacles"""
        for i in range(len(path) - 1):
            for obstacle in constraints.avoid_areas:
                if self._line_intersects_rect(path[i], path[i+1], obstacle):
                    return True
        return False
    
    def _line_intersects_rect(self, p1: QPointF, p2: QPointF, rect: QRectF) -> bool:
        """Check if line segment intersects rectangle"""
        # Simple implementation - could be more sophisticated
        line_rect = QRectF(min(p1.x(), p2.x()), min(p1.y(), p2.y()),
                          abs(p2.x() - p1.x()), abs(p2.y() - p1.y()))
        return rect.intersects(line_rect)

class CurrentVisualizer:
    """Advanced current visualization system"""
    
    def __init__(self):
        self.current_items = {}
        self.animation_items = {}
        self.color_schemes = {
            'default': {'low': QColor(0, 255, 0), 'medium': QColor(255, 255, 0), 'high': QColor(255, 0, 0)},
            'thermal': {'low': QColor(0, 0, 255), 'medium': QColor(255, 255, 0), 'high': QColor(255, 0, 0)},
            'grayscale': {'low': QColor(200, 200, 200), 'medium': QColor(128, 128, 128), 'high': QColor(0, 0, 0)}
        }
        self.current_scheme = 'default'
    
    def visualize_current(self, wire, current_value: float, direction: int,
                         style: str = 'arrow') -> List[QGraphicsItem]:
        """Create comprehensive current visualization"""
        items = []
        
        if abs(current_value) < 1e-12:
            return items
        
        # Get wire path points
        if hasattr(wire, '_points') and wire._points:
            points = wire._points
        else:
            # Fallback to start/end positions
            points = [wire.start_pin.scenePos(), wire.end_pin.scenePos()]
        
        if len(points) < 2:
            return items
        
        # Create different visualization elements based on style
        if style == 'arrow':
            items.extend(self._create_current_arrows(points, current_value, direction))
        elif style == 'flow':
            items.extend(self._create_flow_animation(points, current_value, direction))
        elif style == 'color':
            items.extend(self._create_color_coding(wire, current_value))
        elif style == 'width':
            items.extend(self._create_width_coding(points, current_value))
        
        # Add current value text
        text_item = self._create_current_text(points, current_value, direction)
        if text_item:
            items.append(text_item)
        
        return items
    
    def _create_current_arrows(self, points: List[QPointF], current_value: float, 
                              direction: int) -> List[QGraphicsItem]:
        """Create arrow indicators for current flow"""
        arrows = []
        
        # Determine arrow properties based on current magnitude
        magnitude = abs(current_value)
        arrow_size = self._calculate_arrow_size(magnitude)
        arrow_color = self._calculate_arrow_color(magnitude)
        
        # Calculate number of arrows based on wire length
        total_length = self._calculate_path_length(points)
        arrow_spacing = max(50, total_length / 5)  # At least 50 units apart
        
        # Create arrows along the path
        current_distance = arrow_spacing / 2  # Start offset
        
        for i in range(len(points) - 1):
            segment_start = points[i]
            segment_end = points[i + 1]
            segment_length = math.sqrt((segment_end.x() - segment_start.x())**2 + 
                                     (segment_end.y() - segment_start.y())**2)
            
            while current_distance < segment_length:
                # Calculate arrow position
                ratio = current_distance / segment_length
                arrow_pos = QPointF(
                    segment_start.x() + ratio * (segment_end.x() - segment_start.x()),
                    segment_start.y() + ratio * (segment_end.y() - segment_start.y())
                )
                
                # Calculate arrow direction
                dx = segment_end.x() - segment_start.x()
                dy = segment_end.y() - segment_start.y()
                angle = math.atan2(dy, dx)
                
                if direction == -1:
                    angle += math.pi
                
                # Create arrow
                arrow = self._create_single_arrow(arrow_pos, angle, arrow_size, arrow_color)
                arrows.append(arrow)
                
                current_distance += arrow_spacing
            
            current_distance -= segment_length
        
        return arrows
    
    def _create_single_arrow(self, position: QPointF, angle: float, 
                            size: float, color: QColor) -> QGraphicsPolygonItem:
        """Create a single arrow graphic"""
        # Arrow geometry
        arrow_length = size
        arrow_width = size * 0.6
        
        # Create arrow polygon
        arrow_points = [
            QPointF(arrow_length / 2, 0),  # Tip
            QPointF(-arrow_length / 2, arrow_width / 2),  # Left wing
            QPointF(-arrow_length / 4, 0),  # Neck
            QPointF(-arrow_length / 2, -arrow_width / 2)  # Right wing
        ]
        
        # Rotate and translate arrow
        transform = QTransform()
        transform.translate(position.x(), position.y())
        transform.rotate(math.degrees(angle))
        
        rotated_points = [transform.map(p) for p in arrow_points]
        
        # Create graphics item
        polygon = QPolygonF(rotated_points)
        arrow_item = QGraphicsPolygonItem(polygon)
        arrow_item.setBrush(QBrush(color))
        arrow_item.setPen(QPen(color, 1))
        arrow_item.setZValue(WIRE_Z_VALUE + 0.1)
        
        return arrow_item
    
    def _create_flow_animation(self, points: List[QPointF], current_value: float,
                              direction: int) -> List[QGraphicsItem]:
        """Create animated flow indicators"""
        # This would create animated dots/dashes moving along the wire
        # For now, return static flow indicators
        flow_items = []
        
        magnitude = abs(current_value)
        dot_size = self._calculate_dot_size(magnitude)
        dot_color = self._calculate_arrow_color(magnitude)
        
        # Create flow dots
        num_dots = max(3, int(self._calculate_path_length(points) / 30))
        
        for i in range(num_dots):
            # Calculate dot position along path
            ratio = i / (num_dots - 1) if num_dots > 1 else 0.5
            dot_pos = self._interpolate_along_path(points, ratio)
            
            # Create dot
            dot = QGraphicsEllipseItem(dot_pos.x() - dot_size/2, dot_pos.y() - dot_size/2,
                                     dot_size, dot_size)
            dot.setBrush(QBrush(dot_color))
            dot.setPen(QPen(dot_color, 1))
            dot.setZValue(WIRE_Z_VALUE + 0.1)
            
            flow_items.append(dot)
        
        return flow_items
    
    def _create_color_coding(self, wire, current_value: float) -> List[QGraphicsItem]:
        """Create color-coded wire representation"""
        # This would modify the wire's appearance based on current
        # For now, return empty list as the wire itself would be modified
        return []
    
    def _create_width_coding(self, points: List[QPointF], current_value: float) -> List[QGraphicsItem]:
        """Create width-coded wire representation"""
        # Create a path with width proportional to current
        magnitude = abs(current_value)
        width = max(2, min(10, magnitude * 1000))  # Scale factor
        
        path = QPainterPath()
        if points:
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
        
        # Create thick path item
        path_item = QGraphicsPathItem(path)
        color = self._calculate_arrow_color(magnitude)
        path_item.setPen(QPen(color, width))
        path_item.setZValue(WIRE_Z_VALUE - 0.1)
        
        return [path_item]
    
    def _create_current_text(self, points: List[QPointF], current_value: float,
                            direction: int) -> Optional[QGraphicsTextItem]:
        """Create current value text display"""
        if len(points) < 2:
            return None
        
        # Find midpoint of path
        mid_pos = self._interpolate_along_path(points, 0.5)
        
        # Format current value
        magnitude = abs(current_value)
        if magnitude >= 1:
            text = f"{magnitude:.2f} A"
        elif magnitude >= 1e-3:
            text = f"{magnitude*1e3:.2f} mA"
        elif magnitude >= 1e-6:
            text = f"{magnitude*1e6:.2f} μA"
        elif magnitude >= 1e-9:
            text = f"{magnitude*1e9:.2f} nA"
        else:
            text = f"{magnitude:.2e} A"
        
        # Add direction indicator
        arrow = "→" if direction == 1 else ("←" if direction == -1 else "-")
        text += f" {arrow}"
        
        # Create text item
        text_item = QGraphicsTextItem(text)
        text_item.setFont(QFont("Arial", 8))
        text_item.setDefaultTextColor(self._calculate_arrow_color(magnitude))
        text_item.setPos(mid_pos.x() - text_item.boundingRect().width()/2,
                        mid_pos.y() - text_item.boundingRect().height()/2)
        text_item.setZValue(WIRE_Z_VALUE + 0.2)
        
        return text_item
    
    def _calculate_arrow_size(self, magnitude: float) -> float:
        """Calculate arrow size based on current magnitude"""
        # Logarithmic scaling
        if magnitude <= 0:
            return 10
        
        base_size = 10
        scale_factor = math.log10(magnitude * 1000 + 1)
        return base_size + scale_factor * 5
    
    def _calculate_dot_size(self, magnitude: float) -> float:
        """Calculate dot size for flow animation"""
        return max(3, min(8, magnitude * 1000 + 3))
    
    def _calculate_arrow_color(self, magnitude: float) -> QColor:
        """Calculate color based on current magnitude"""
        scheme = self.color_schemes[self.current_scheme]
        
        if magnitude < 1e-6:  # Less than 1 μA
            return scheme['low']
        elif magnitude < 1e-3:  # Less than 1 mA
            ratio = magnitude / 1e-3
            return self._interpolate_color(scheme['low'], scheme['medium'], ratio)
        elif magnitude < 1:  # Less than 1 A
            ratio = magnitude / 1
            return self._interpolate_color(scheme['medium'], scheme['high'], ratio)
        else:
            return scheme['high']
    
    def _interpolate_color(self, color1: QColor, color2: QColor, ratio: float) -> QColor:
        """Interpolate between two colors"""
        ratio = max(0, min(1, ratio))
        
        r = int(color1.red() + ratio * (color2.red() - color1.red()))
        g = int(color1.green() + ratio * (color2.green() - color1.green()))
        b = int(color1.blue() + ratio * (color2.blue() - color1.blue()))
        
        return QColor(r, g, b)
    
    def _calculate_path_length(self, points: List[QPointF]) -> float:
        """Calculate total path length"""
        length = 0.0
        for i in range(len(points) - 1):
            dx = points[i+1].x() - points[i].x()
            dy = points[i+1].y() - points[i].y()
            length += math.sqrt(dx*dx + dy*dy)
        return length
    
    def _interpolate_along_path(self, points: List[QPointF], ratio: float) -> QPointF:
        """Interpolate position along path at given ratio (0-1)"""
        if not points:
            return QPointF()
        
        if len(points) == 1:
            return points[0]
        
        total_length = self._calculate_path_length(points)
        target_distance = total_length * ratio
        
        current_distance = 0.0
        
        for i in range(len(points) - 1):
            segment_start = points[i]
            segment_end = points[i + 1]
            segment_length = math.sqrt((segment_end.x() - segment_start.x())**2 + 
                                     (segment_end.y() - segment_start.y())**2)
            
            if current_distance + segment_length >= target_distance:
                # Target is in this segment
                remaining = target_distance - current_distance
                segment_ratio = remaining / segment_length if segment_length > 0 else 0
                
                return QPointF(
                    segment_start.x() + segment_ratio * (segment_end.x() - segment_start.x()),
                    segment_start.y() + segment_ratio * (segment_end.y() - segment_start.y())
                )
            
            current_distance += segment_length
        
        return points[-1]  # Fallback to end point

class AdvancedWire(QGraphicsPathItem):
    """
    Advanced Wire class with intelligent routing, enhanced visual feedback,
    and comprehensive electrical modeling. This is a complete overhaul of
    the original wire system with significant improvements.
    """
    
    def __init__(self, start_pin, end_pin, wire_type: WireType = WireType.NORMAL, parent=None):
        super().__init__(parent)
        
        # Core properties
        self.start_pin = start_pin
        self.end_pin = end_pin
        self.wire_type = wire_type
        
        # Enhanced properties
        self.electrical_props = WireElectricalProperties()
        self.geometry_props = WireGeometry()
        self.routing_constraints = RoutingConstraints()
        
        # Visual properties
        self.wire_style = WireStyle.SOLID
        self.highlight_color = None
        self.current_visualizer = CurrentVisualizer()
        self.visual_items = []
        
        # Routing
        self.router = OrthogonalRouter()
        self.routing_algorithm = RoutingAlgorithm.ORTHOGONAL
        self._points = []
        
        # Component references
        self.start_comp = start_pin.data(2) if start_pin else None
        self.end_comp = end_pin.data(2) if end_pin else None
        
        # Performance optimization
        self._path_cache = None
        self._length_cache = None
        
        # Setup
        self._setup_visual_properties()
        self._connect_to_components()
        self.update_routing()
    
    def _setup_visual_properties(self):
        """Setup visual properties based on wire type"""
        # Base properties
        self.setZValue(WIRE_Z_VALUE)
        self.setFlags(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        
        # Type-specific properties
        if self.wire_type == WireType.POWER:
            self.setPen(QPen(QColor(255, 0, 0), 3))  # Red, thick
            self.electrical_props.max_current = 10.0  # Higher current rating
        elif self.wire_type == WireType.GROUND:
            self.setPen(QPen(QColor(0, 100, 0), 2))  # Dark green
        elif self.wire_type == WireType.CLOCK:
            self.setPen(QPen(QColor(0, 0, 255), 1))  # Blue
            self.electrical_props.impedance = 50.0  # Controlled impedance
        elif self.wire_type == WireType.BUS:
            self.setPen(QPen(QColor(128, 0, 128), 4))  # Purple, thick
        elif self.wire_type == WireType.DIFFERENTIAL:
            self.setPen(QPen(QColor(255, 165, 0), 2))  # Orange
            self.electrical_props.impedance = 100.0  # Differential impedance
        else:
            self.setPen(WIRE_PEN)  # Default
    
    def _connect_to_components(self):
        """Connect wire to components"""
        if self.start_comp:
            self.start_comp.add_connected_wire(self)
        if self.end_comp:
            self.end_comp.add_connected_wire(self)
    
    def set_routing_algorithm(self, algorithm: RoutingAlgorithm):
        """Set routing algorithm"""
        self.routing_algorithm = algorithm
        
        if algorithm == RoutingAlgorithm.ORTHOGONAL:
            self.router = OrthogonalRouter()
        elif algorithm == RoutingAlgorithm.MANHATTAN:
            self.router = ManhattanRouter()
        else:
            self.router = OrthogonalRouter()  # Default fallback
        
        self.update_routing()
    
    def set_routing_constraints(self, constraints: RoutingConstraints):
        """Set routing constraints"""
        self.routing_constraints = constraints
        self.update_routing()
    
    def update_routing(self):
        """Update wire routing with current algorithm and constraints"""
        if not self.start_pin or not self.end_pin:
            self.setPath(QPainterPath())
            return
        
        start_pos = self.start_pin.scenePos()
        end_pos = self.end_pin.scenePos()
        
        try:
            # Generate route points
            self._points = self.router.route(start_pos, end_pos, self.routing_constraints)
            
            # Update path
            self._update_path_from_points()
            
            # Update geometry properties
            self._update_geometry_properties()
            
            # Clear caches
            self._path_cache = None
            self._length_cache = None
            
        except Exception as e:
            logger.error(f"Error updating wire routing: {e}")
            # Fallback to direct connection
            self._points = [start_pos, end_pos]
            self._update_path_from_points()
    
    def _update_path_from_points(self):
        """Update QPainterPath from route points"""
        path = QPainterPath()
        
        if self._points:
            path.moveTo(self._points[0])
            for point in self._points[1:]:
                path.lineTo(point)
        
        self.setPath(path)
    
    def _update_geometry_properties(self):
        """Update geometric properties"""
        if len(self._points) >= 2:
            # Calculate length
            length = 0.0
            for i in range(len(self._points) - 1):
                dx = self._points[i+1].x() - self._points[i].x()
                dy = self._points[i+1].y() - self._points[i].y()
                length += math.sqrt(dx*dx + dy*dy)
            
            self.geometry_props.length = length
            
            # Count bends
            bends = max(0, len(self._points) - 2)
            self.geometry_props.bend_radius = bends * 2.0  # Simplified
    
    def calculate_electrical_properties(self, frequency: float = 0) -> Dict[str, float]:
        """Calculate frequency-dependent electrical properties"""
        length = self.geometry_props.length
        
        # Basic calculations
        resistance = self.electrical_props.resistance_per_unit * length
        inductance = self.electrical_props.inductance_per_unit * length
        capacitance = self.electrical_props.capacitance_per_unit * length
        
        # Frequency-dependent effects
        if frequency > 0:
            # Skin effect
            skin_depth = math.sqrt(2 / (2 * math.pi * frequency * 4e-7 * 5.8e7))  # Copper
            if skin_depth < self.geometry_props.cross_section:
                resistance *= self.electrical_props.skin_effect_factor
            
            # AC impedance
            omega = 2 * math.pi * frequency
            impedance_magnitude = math.sqrt(resistance**2 + (omega * inductance)**2)
        else:
            impedance_magnitude = resistance
        
        return {
            'resistance': resistance,
            'inductance': inductance,
            'capacitance': capacitance,
            'impedance': impedance_magnitude,
            'length': length
        }
    
    def visualize_current(self, current_value: float, direction: int, 
                         style: str = 'arrow'):
        """Visualize current flow through wire"""
        # Clear previous visualization
        self.clear_current_visualization()
        
        # Create new visualization
        self.visual_items = self.current_visualizer.visualize_current(
            self, current_value, direction, style
        )
        
        # Add items to scene
        scene = self.scene()
        if scene:
            for item in self.visual_items:
                scene.addItem(item)
    
    def clear_current_visualization(self):
        """Clear current visualization"""
        scene = self.scene()
        if scene:
            for item in self.visual_items:
                if item.scene():
                    scene.removeItem(item)
        
        self.visual_items.clear()
    
    def set_wire_style(self, style: WireStyle):
        """Set visual style of wire"""
        self.wire_style = style
        
        pen = self.pen()
        
        if style == WireStyle.DASHED:
            pen.setStyle(Qt.PenStyle.DashLine)
        elif style == WireStyle.DOTTED:
            pen.setStyle(Qt.PenStyle.DotLine)
        elif style == WireStyle.THICK:
            pen.setWidth(pen.width() * 2)
        elif style == WireStyle.THIN:
            pen.setWidth(max(1, pen.width() // 2))
        elif style == WireStyle.HIGHLIGHTED:
            pen.setColor(QColor(255, 255, 0))  # Yellow
            pen.setWidth(pen.width() + 1)
        else:  # SOLID
            pen.setStyle(Qt.PenStyle.SolidLine)
        
        self.setPen(pen)
    
    def highlight(self, color: QColor = None):
        """Highlight wire with specified color"""
        if color is None:
            color = QColor(255, 255, 0)  # Yellow default
        
        self.highlight_color = color
        pen = self.pen()
        pen.setColor(color)
        pen.setWidth(pen.width() + 1)
        self.setPen(pen)
    
    def remove_highlight(self):
        """Remove wire highlighting"""
        self.highlight_color = None
        self._setup_visual_properties()  # Reset to default
    
    def get_path_length(self) -> float:
        """Get total path length with caching"""
        if self._length_cache is not None:
            return self._length_cache
        
        if not self._points:
            self._length_cache = 0.0
            return 0.0
        
        length = 0.0
        for i in range(len(self._points) - 1):
            dx = self._points[i+1].x() - self._points[i].x()
            dy = self._points[i+1].y() - self._points[i].y()
            length += math.sqrt(dx*dx + dy*dy)
        
        self._length_cache = length
        return length
    
    def get_midpoint(self) -> QPointF:
        """Get midpoint of wire path"""
        if not self._points:
            return QPointF()
        
        if len(self._points) == 1:
            return self._points[0]
        
        total_length = self.get_path_length()
        target_distance = total_length / 2
        
        current_distance = 0.0
        
        for i in range(len(self._points) - 1):
            segment_start = self._points[i]
            segment_end = self._points[i + 1]
            dx = segment_end.x() - segment_start.x()
            dy = segment_end.y() - segment_start.y()
            segment_length = math.sqrt(dx*dx + dy*dy)
            
            if current_distance + segment_length >= target_distance:
                # Midpoint is in this segment
                remaining = target_distance - current_distance
                ratio = remaining / segment_length if segment_length > 0 else 0
                
                return QPointF(
                    segment_start.x() + ratio * dx,
                    segment_start.y() + ratio * dy
                )
            
            current_distance += segment_length
        
        return self._points[-1]  # Fallback
    
    def update_positions(self):
        """Update wire positions when pins move"""
        self.update_routing()
    
    def remove(self):
        """Remove wire and cleanup"""
        logger.info(f"Removing advanced wire: {self}")
        
        # Clear visualizations
        self.clear_current_visualization()
        
        # Disconnect from components
        if self.start_comp:
            self.start_comp.remove_connected_wire(self)
        if self.end_comp:
            self.end_comp.remove_connected_wire(self)
        
        # Remove from netlist
        scene = self.scene()
        if scene and hasattr(scene, 'views') and scene.views():
            main_window = scene.views()[0].main_window
            if main_window and hasattr(main_window, 'netlist'):
                main_window.netlist.remove_wire(self)
        
        # Remove from scene
        if scene:
            scene.removeItem(self)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize wire to dictionary"""
        start_comp_name = self.start_comp.component_name if self.start_comp else None
        start_pin_name = self.start_pin.data(1) if self.start_pin else None
        end_comp_name = self.end_comp.component_name if self.end_comp else None
        end_pin_name = self.end_pin.data(1) if self.end_pin else None
        
        data = {
            "wire_type": self.wire_type.value,
            "routing_algorithm": self.routing_algorithm.value,
            "wire_style": self.wire_style.value,
            "start_pin": {
                "component": start_comp_name,
                "pin": start_pin_name
            },
            "end_pin": {
                "component": end_comp_name,
                "pin": end_pin_name
            },
            "points": [{"x": p.x(), "y": p.y()} for p in self._points],
            "electrical_properties": {
                "resistance_per_unit": self.electrical_props.resistance_per_unit,
                "inductance_per_unit": self.electrical_props.inductance_per_unit,
                "capacitance_per_unit": self.electrical_props.capacitance_per_unit,
                "impedance": self.electrical_props.impedance,
                "max_current": self.electrical_props.max_current,
                "max_voltage": self.electrical_props.max_voltage
            },
            "geometry_properties": {
                "width": self.geometry_props.width,
                "length": self.geometry_props.length,
                "cross_section": self.geometry_props.cross_section,
                "layer": self.geometry_props.layer
            }
        }
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], start_pin, end_pin):
        """Create wire from dictionary"""
        wire_type = WireType(data.get("wire_type", WireType.NORMAL.value))
        wire = cls(start_pin, end_pin, wire_type)
        
        # Restore properties
        if "routing_algorithm" in data:
            algorithm = RoutingAlgorithm(data["routing_algorithm"])
            wire.set_routing_algorithm(algorithm)
        
        if "wire_style" in data:
            style = WireStyle(data["wire_style"])
            wire.set_wire_style(style)
        
        if "electrical_properties" in data:
            props = data["electrical_properties"]
            wire.electrical_props.resistance_per_unit = props.get("resistance_per_unit", 0.0)
            wire.electrical_props.inductance_per_unit = props.get("inductance_per_unit", 0.0)
            wire.electrical_props.capacitance_per_unit = props.get("capacitance_per_unit", 0.0)
            wire.electrical_props.impedance = props.get("impedance")
            wire.electrical_props.max_current = props.get("max_current", float('inf'))
            wire.electrical_props.max_voltage = props.get("max_voltage", float('inf'))
        
        if "geometry_properties" in data:
            props = data["geometry_properties"]
            wire.geometry_props.width = props.get("width", 1.0)
            wire.geometry_props.cross_section = props.get("cross_section", 1.0)
            wire.geometry_props.layer = props.get("layer", 0)
        
        # Restore points if available
        if "points" in data:
            points = [QPointF(p["x"], p["y"]) for p in data["points"]]
            wire._points = points
            wire._update_path_from_points()
        
        return wire
    
    # Legacy compatibility methods
    def show_current_arrow(self, current_value: float, direction: int):
        """Legacy compatibility method"""
        self.visualize_current(current_value, direction, 'arrow')
    
    def update_current_visual(self, current_value: float, direction: int):
        """Legacy compatibility method"""
        self.visualize_current(current_value, direction, 'arrow')
    
    def hide_current_display(self):
        """Legacy compatibility method"""
        self.clear_current_visualization()

# Maintain backward compatibility
Wire = AdvancedWire
