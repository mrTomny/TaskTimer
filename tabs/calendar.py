from PyQt6.QtWidgets import QCalendarWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QFont
from tabs.themes import get_theme_palette

class ModernCalendarWidget(QCalendarWidget):
    def __init__(self, parent=None, get_theme_cb=None):
        super().__init__(parent)
        self.get_theme_cb = get_theme_cb  #раздавать палитру текущей темы
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers)
        self.setFont(QFont("Segoe UI", 11))

    def paintCell(self, painter: QPainter, rect: QRectF, date):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        theme_name = self.get_theme_cb() if self.get_theme_cb else 'dark_fantasy'
        pal = get_theme_palette(theme_name)
        
        is_selected = (date == self.selectedDate())
        is_today = (date == date.currentDate())

        # Пропорциональный отступ от границ ячейки — делает аккуратную капсулу внутри ячейки
        pill_rect = rect.adjusted(6, 6, -6, -6)

        if is_selected:
            painter.setBrush(QBrush(QColor(pal['in_progress'])))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pill_rect, 10, 10)
            
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            
        elif is_today:
            painter.setBrush(QBrush(QColor(pal['menu_sel'])))
            painter.setPen(QColor(pal['in_progress']))
            painter.drawRoundedRect(pill_rect, 10, 10)
            
            painter.setPen(QColor(pal['menu_fg']))
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            
        else:
            if date.dayOfWeek() >= 6:
                painter.setPen(QColor(pal['expired']))
            else:
                painter.setPen(QColor(pal['menu_fg']))
                
            painter.setFont(QFont("Segoe UI", 11))

        # Рисуем цифру строго по центру
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(date.day()))
        
        painter.restore()