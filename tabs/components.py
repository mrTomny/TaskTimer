import os
import re
from datetime import datetime, timezone, timedelta
from tabs.events import events

from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QFont, QBrush, QPainterPath
from PyQt6.QtWidgets import QWidget, QApplication, QFileDialog, QVBoxLayout, QLabel, QPushButton

class BaseMiniPlayer(QWidget):
    add_task_requested = pyqtSignal()
    return_requested = pyqtSignal()

    def __init__(self, parent=None, tz_offset=3):
        super().__init__(parent)
        self.tz_offset = tz_offset
        self.task_created_dt = None
        self.closest_task_dt = None
        self.theme_palette = None
        self.current_progress = 0.0
        
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Плеер сам слушает глобальный пульс!
        events.timer_tick.connect(self.update_ui)
        
    def on_task_started(self, task_name, start_dt, end_dt):
        """Срабатывает, когда контроллер сообщает о старте задачи"""
        time_str = end_dt.strftime("%H:%M") if end_dt else ""
        
        # Обновляем текст на экране
        self.set_task_text(f"⏳ {time_str} | {task_name}")
        
        # Запоминаем время для анимации песка/круга
        self.closest_task_dt = end_dt
        self.task_created_dt = start_dt

    def on_task_stopped(self):
        """Срабатывает, когда задача завершена или отменена"""
        self.set_task_text("Нет активных задач")
        self.closest_task_dt = None
        self.task_created_dt = None
        self.current_progress = 0.0  # Сбрасываем песок
        self.update() # Перерисовываем пустые часы

    def set_task_text(self, text):
        for lbl_name in ('info_lbl', 'lbl_task'):
            if hasattr(self, lbl_name):
                lbl = getattr(self, lbl_name)
                if hasattr(lbl, 'setText'):
                    lbl.setToolTip(text)
                    lbl.setText(text)
                    break

    def apply_theme(self, palette):
        self.theme_palette = palette
        self.update()

    def update_ui(self):
        current_tz = timezone(timedelta(hours=self.tz_offset))
        now = datetime.now(current_tz)
        
        # Безопасно обновляем время для любого типа плеера
        for time_lbl_name in ('time_lbl', 'lbl_time'):
            if hasattr(self, time_lbl_name):
                lbl = getattr(self, time_lbl_name)
                if hasattr(lbl, 'setText'):
                    lbl.setText(now.strftime("%H:%M:%S"))
                break
        
        if self.task_created_dt and self.closest_task_dt:
            try:
                start_dt = self.task_created_dt
                end_dt = self.closest_task_dt
                
                # Защита: если одна дата с часовым поясом, а вторая без — приводим обе к offset-naive (без зон) для безопасного вычитания
                if start_dt.tzinfo is not None and end_dt.tzinfo is None:
                    start_dt = start_dt.astimezone(current_tz).replace(tzinfo=None)
                elif start_dt.tzinfo is None and end_dt.tzinfo is not None:
                    end_dt = end_dt.astimezone(current_tz).replace(tzinfo=None)
                elif start_dt.tzinfo is not None and end_dt.tzinfo is not None:
                    start_dt = start_dt.astimezone(current_tz).replace(tzinfo=None)
                    end_dt = end_dt.astimezone(current_tz).replace(tzinfo=None)

                total = (end_dt - start_dt).total_seconds()
                
                # Текущее время тоже переводим в naive для расчета прошедших секунд
                now_naive = now.replace(tzinfo=None)
                elapsed = (now_naive - start_dt).total_seconds()
                
                self.current_progress = max(0.0, min(1.0, elapsed / total)) if total > 0 else 1.0
            except Exception as e:
                # Если вдруг что-то пойдет не так, просто сбрасываем прогресс вместо краша программы
                self.current_progress = 0.0
                
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_pos'):
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.return_requested.emit()
            event.accept()


class HourglassMiniPlayer(BaseMiniPlayer):
    def __init__(self, parent=None, tz_offset=3):
        super().__init__(parent, tz_offset)
        self.setFixedSize(240, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        # Точно настраиваем отступы, чтобы текст и кнопки находились внутри стекла
        layout.setContentsMargins(30, 65, 30, 45)
        layout.setSpacing(6)

        # Время
        self.time_lbl = QLabel("--:--:--")
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_lbl.setStyleSheet("""
            color: white; 
            font-size: 16px; 
            font-weight: bold; 
            background: rgba(0, 0, 0, 0.4); 
            border-radius: 6px; 
            padding: 2px 8px;
        """)
        
        # Кнопка задачи
        self.btn_add = QPushButton("➕ Задача")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 0.4);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                border-color: white;
            }
        """)
        self.btn_add.clicked.connect(self.add_task_requested.emit)

        # Текст задачи (аккуратно над нижней подставкой)
        self.info_lbl = QLabel("Нет активных задач")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet("""
            color: white; 
            font-size: 11px; 
            background: rgba(15, 15, 15, 0.7); 
            border-radius: 6px; 
            padding: 6px; 
            font-weight: bold;
        """)

        layout.addWidget(self.time_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.btn_add, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        layout.addWidget(self.info_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        center_x, center_y = w / 2, h / 2

        top_bulb_top = 95       
        bottom_bulb_bottom = h - 75 

        # 1. РИСУЕМ КАРКАС И СТЕКЛО (Векторная графика)
        # Получаем цвета из темы
        stand_color = QColor(40, 40, 40, 240)
        border_color = QColor(100, 100, 100, 150)
        if self.theme_palette:
            if 'cal_comp_bg' in self.theme_palette:
                stand_color = QColor(self.theme_palette['cal_comp_bg'])
                stand_color.setAlpha(240)
            if 'version' in self.theme_palette:
                border_color = QColor(self.theme_palette['version'])

        painter.setBrush(QBrush(stand_color))
        painter.setPen(QPen(border_color, 2))
        
        # Стойки (колонны по бокам)
        painter.drawRoundedRect(QRectF(45, top_bulb_top, 8, bottom_bulb_bottom - top_bulb_top), 4, 4)
        painter.drawRoundedRect(QRectF(w - 53, top_bulb_top, 8, bottom_bulb_bottom - top_bulb_top), 4, 4)
        
        # Верхняя и нижняя крышки (подставки)
        painter.drawRoundedRect(QRectF(35, top_bulb_top - 15, w - 70, 15), 4, 4)
        painter.drawRoundedRect(QRectF(35, bottom_bulb_bottom, w - 70, 15), 4, 4)

        # Контуры колбы (стекло)
        glass_top = QPainterPath()
        glass_top.moveTo(74, top_bulb_top)
        glass_top.lineTo(w - 74, top_bulb_top)
        glass_top.quadTo(w - 80, center_y - 30, center_x + 2, center_y)
        glass_top.lineTo(center_x - 2, center_y)
        glass_top.quadTo(80, center_y - 30, 74, top_bulb_top)
        glass_top.closeSubpath()

        glass_bottom = QPainterPath()
        glass_bottom.moveTo(center_x - 2, center_y)
        glass_bottom.lineTo(center_x + 2, center_y)
        glass_bottom.quadTo(w - 80, center_y + 30, w - 74, bottom_bulb_bottom)
        glass_bottom.lineTo(74, bottom_bulb_bottom)
        glass_bottom.quadTo(80, center_y + 30, center_x - 2, center_y)
        glass_bottom.closeSubpath()

       # Определяем, светлая ли сейчас тема (если рамки темные, значит фон светлый)
        is_light_theme = border_color.lightness() < 128

        # Заливка стекла (очень легкая)
        glass_bg = QColor(0, 0, 0, 15) if is_light_theme else QColor(255, 255, 255, 10)
        glass_brush = QBrush(glass_bg)
        
        # Контур стекла (отвязан от цвета стоек, теперь это имитация прозрачного стекла)
        glass_outline = QColor(0, 0, 0, 70) if is_light_theme else QColor(255, 255, 255, 70)
        glass_pen = QPen(glass_outline, 2)
        
        painter.setBrush(glass_brush)
        painter.setPen(glass_pen)
        painter.drawPath(glass_top)
        painter.drawPath(glass_bottom)

        # Блики на стекле (более контрастные для объема)
        highlight_color = QColor(0, 0, 0, 30) if is_light_theme else QColor(255, 255, 255, 90)
        highlight_pen = QPen(highlight_color, 3)
        highlight_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(highlight_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(78, top_bulb_top + 10, 30, 50), 100 * 16, 50 * 16)
        painter.drawArc(QRectF(w - 108, bottom_bulb_bottom - 60, 30, 50), 280 * 16, 50 * 16)


        # 2. РИСУЕМ ПЕСОК
        progress = getattr(self, 'current_progress', 0.0)
        
        hex_color = "#ECB753"  # Приятный золотисто-песочный оттенок
        sand_color = QColor(hex_color)
        sand_color.setAlpha(210) # Делаем песок чуть плотнее для реалистичности 

        # Верхний песок (убывает)
        if progress < 1.0:
            painter.save()
            painter.setClipPath(glass_top)
            painter.setBrush(QBrush(sand_color))
            painter.setPen(Qt.PenStyle.NoPen)
            sand_height = (center_y - top_bulb_top) * (1.0 - progress)
            painter.drawRect(QRectF(0, center_y - sand_height, w, sand_height))
            painter.restore()
            
            # Тонкая струйка
            bulb_height = bottom_bulb_bottom - center_y
            bottom_sand_h = bulb_height * progress
            painter.setPen(QPen(sand_color, 2))
            painter.drawLine(QPointF(center_x, center_y), QPointF(center_x, bottom_bulb_bottom - bottom_sand_h))

        # Нижний песок (накапливается)
        if progress > 0.0:
            painter.save()
            painter.setClipPath(glass_bottom)
            painter.setBrush(QBrush(sand_color))
            painter.setPen(Qt.PenStyle.NoPen)
            bulb_height = bottom_bulb_bottom - center_y
            sand_height = bulb_height * progress
            painter.drawRect(QRectF(0, bottom_bulb_bottom - sand_height, w, sand_height))
            painter.restore()


class CircularMiniPlayer(BaseMiniPlayer):
    def __init__(self, parent=None, tz_offset=3):
        super().__init__(parent, tz_offset)
        self.setFixedSize(280, 280)
        self.current_opacity = 0.95
        self.setWindowOpacity(self.current_opacity)

        self.bg_color = QColor(25, 25, 25, 230)
        self.arc_color = QColor("#3498db")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_time = QLabel("00:00:00")
        self.lbl_time.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_task = QLabel("Нет активных задач")
        self.lbl_task.setFont(QFont("Segoe UI", 12))
        self.lbl_task.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_task.setWordWrap(True)

        self.btn_quick_add = QPushButton("+", self)
        self.btn_quick_add.setFixedSize(30, 30) 
        self.btn_quick_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quick_add.setStyleSheet("""
            QPushButton {
                border-radius: 15px;
                background-color: #3498db;
                color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 26px; 
                padding-bottom: 3px; 
                border: none;
            }
            QPushButton:hover { 
                background-color: #2980b9; 
            }
        """)
        self.btn_quick_add.clicked.connect(self.add_task_requested.emit)

        layout.addWidget(self.btn_quick_add, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.lbl_time, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.lbl_task, alignment=Qt.AlignmentFlag.AlignHCenter)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.current_opacity = min(1.0, self.current_opacity + 0.05)
        else:
            self.current_opacity = max(0.2, self.current_opacity - 0.05)
        self.setWindowOpacity(self.current_opacity)

    def apply_theme(self, palette):
        super().apply_theme(palette)
        bg_hex = palette.get('history_bg', '#1e1e1e')
        base_bg = QColor(bg_hex)
        base_bg.setAlpha(230)
        self.bg_color = base_bg
        self.arc_color = QColor(palette.get('in_progress', '#3498db'))        
        text_color = palette.get('clock', 'white')
        subtext_color = palette.get('menu_fg', '#cccccc')
        self.lbl_time.setStyleSheet(f"color: {text_color};")
        self.lbl_task.setStyleSheet(f"color: {subtext_color};")
        btn_bg = palette.get('in_progress', '#3498db')
        self.btn_quick_add.setStyleSheet(f"""
            QPushButton {{
                border-radius: 15px;
                background-color: {btn_bg};
                color: white;
                font-family: Arial, sans-serif;
                font-weight: bold;
                font-size: 28px;
                padding-bottom: 3px;
                border: none;
            }}
            QPushButton:hover {{ 
                background-color: {palette.get('accent', '#2980b9')}; 
            }}
        """)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -8)    
        painter.setBrush(self.bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)
        pen = QPen(self.arc_color)
        pen.setWidth(6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        progress = getattr(self, 'current_progress', 0.0)

        if progress > 0:
            span_angle = int(-360 * progress * 16)
            start_angle = 90 * 16         
            painter.drawArc(rect, start_angle, span_angle)
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.return_requested.emit()
            event.accept()


class SquareMiniPlayer(BaseMiniPlayer):
    def __init__(self, parent=None, tz_offset=3):
        super().__init__(parent, tz_offset)
        self.setFixedSize(320, 180)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.time_lbl = QLabel("--:--:--")
        self.time_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_lbl.setStyleSheet("color: white; background: transparent;")

        self.btn_add = QPushButton("➕ Задать задачу")
        self.btn_add.setStyleSheet("background: rgba(255,255,255,0.2); color: white; border-radius: 8px; padding: 6px;")
        self.btn_add.clicked.connect(self.add_task_requested.emit)

        self.info_lbl = QLabel("Нет активных задач")
        self.info_lbl.setFont(QFont("Segoe UI", 10))
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet("color: white; background: transparent;")

        layout.addWidget(self.time_lbl)
        layout.addWidget(self.btn_add)
        layout.addWidget(self.info_lbl)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bg_color = QColor(30, 30, 30, 230)
        if self.theme_palette and 'history_bg' in self.theme_palette:
            bg_color = QColor(self.theme_palette['history_bg'])
            bg_color.setAlpha(230)

        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(QColor(100, 100, 100, 150), 2))
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 12, 12)


class SnippingWidget(QWidget):
    def __init__(self, client_name, save_dir, on_capture_callback):
        super().__init__()
        self.client_name, self.save_dir, self.on_capture_callback = client_name, save_dir, on_capture_callback
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        
        geometry = QRect()
        for screen in QApplication.screens(): geometry = geometry.united(screen.geometry())
        self.setGeometry(geometry)
        
        self.original_pixmap = QPixmap(geometry.size())
        painter = QPainter(self.original_pixmap)
        for screen in QApplication.screens():
            offset = screen.geometry().topLeft() - geometry.topLeft()
            painter.drawPixmap(offset, screen.grabWindow(0))
        painter.end()
        
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.begin = self.end = QPoint()
        self.is_drawing = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.original_pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        if self.is_drawing:
            rect = QRect(self.begin, self.end).normalized()
            painter.drawPixmap(rect, self.original_pixmap.copy(rect))
            pen = QPen(QColor("#00a8ff")); pen.setWidth(2)
            painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

    def mousePressEvent(self, event): self.begin = self.end = event.pos(); self.is_drawing = True; self.update()
    def mouseMoveEvent(self, event): self.end = event.pos(); self.update()
    def mouseReleaseEvent(self, event):
        self.is_drawing = False
        rect = QRect(self.begin, self.end).normalized()
        self.hide()
        
        file_path_saved = None
        if rect.width() > 10 and rect.height() > 10:
            capture = self.original_pixmap.copy(rect)
            safe_name = re.sub(r'[\\/*?:"<>|]', "", self.client_name).strip() or f"Screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            default_filename = f"{safe_name}.png"
            target_dir = self.save_dir if (self.save_dir and os.path.exists(self.save_dir)) else ""
            file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить скриншот", os.path.join(target_dir, default_filename), "Images (*.png *.jpg)")
            if file_path: capture.save(file_path); file_path_saved = file_path
        
        if self.on_capture_callback: self.on_capture_callback(file_path_saved)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.on_capture_callback: self.on_capture_callback(None)
            self.close()