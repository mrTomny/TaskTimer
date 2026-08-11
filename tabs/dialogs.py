import os
import re
import uuid
import platform
import webbrowser
from tabs.logger import log
from datetime import datetime, timezone, timedelta
from tabs.models import Task, HistoryEvent
from tabs.themes import get_theme_palette, get_tag_colors
from tabs.utils import get_app_dir, GITHUB_ISSUES_URL


from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton,
    QFrame, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox,
    QListWidget, QListWidgetItem, QMessageBox, QCalendarWidget, QWidget,
    QTextEdit, QTextBrowser, QApplication, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QDate, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QFont, QColor, QCursor

# --- Вспомогательная функция для парсинга дат ---
def smart_parse_datetime(date_str, time_str, base_tz_offset=3):
    date_str = date_str.strip().lower()
    time_str = time_str.strip()
    
    current_tz = timezone(timedelta(hours=base_tz_offset))
    current_dt = datetime.now(current_tz)
    target_date = current_dt.date()
    target_time = current_dt.time().replace(second=0, microsecond=0)
    
    if not date_str or "сегодня" in date_str: pass
    elif "завтра" in date_str: target_date = current_dt.date() + timedelta(days=1)
    elif "послезавтра" in date_str: target_date = current_dt.date() + timedelta(days=2)
    else:
        digits = re.findall(r'\d+', date_str)
        if digits:
            day = int(digits[0])
            month = int(digits[1]) if len(digits) > 1 else current_dt.month
            year_val = digits[2] if len(digits) > 2 else str(current_dt.year)
            year = 2000 + int(year_val) if len(year_val) == 2 else int(year_val)
            try: target_date = datetime(year, month, day).date()
            except ValueError: pass
        else:
            weekdays = {"понедельник": 0, "вторник": 1, "среда": 2, "четверг": 3, "пятница": 4, "суббота": 5, "воскресенье": 6}
            for w_name, w_idx in weekdays.items():
                if w_name in date_str:
                    days_ahead = (w_idx - current_dt.weekday() + 7) % 7
                    if days_ahead == 0: days_ahead = 7
                    target_date = current_dt.date() + timedelta(days=days_ahead)
                    break

    time_parsed = False
    
    if time_str:
        time_digits = re.findall(r'\d+', time_str)
        if len(time_digits) >= 2:
            hour, minute = int(time_digits[0]), int(time_digits[1])
            if 0 <= hour < 24 and 0 <= minute < 60:
                target_time = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").time()
                time_parsed = True
        elif len(time_digits) == 1:
            digit_str = time_digits[0]
            if len(digit_str) == 4:
                hour, minute = int(digit_str[:2]), int(digit_str[2:])
            elif len(digit_str) == 3:
                hour, minute = int(digit_str[:1]), int(digit_str[1:])
            else:
                hour, minute = int(digit_str), 0
                
            if 0 <= hour < 24 and 0 <= minute < 60:
                target_time = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").time()
                time_parsed = True

    # Если распарсить по цифрам не удалось, но пользователь что-то ввёл ручками — 
    # попробуем вернуть исходную строку или надежный дефолт, вместо того чтобы подставлять "текущее + час"
    final_time_str = target_time.strftime("%H:%M") if time_parsed else (time_str if time_str else target_time.strftime("%H:%M"))

    return target_date.strftime("%d.%m.%Y"), final_time_str

def select_date_via_calendar(parent_widget, current_date_text):
    """Открывает календарь и возвращает выбранную дату в виде строки, либо None."""
    dialog = QDialog(parent_widget)
    dialog.setWindowTitle("Выбор даты")
    dialog.resize(320, 250)
    l = QVBoxLayout(dialog)
    
    cal = QCalendarWidget()
    cal.setGridVisible(True)
    try:
        dt = datetime.strptime(current_date_text, "%d.%m.%Y")
        cal.setSelectedDate(QDate(dt.year, dt.month, dt.day))
    except ValueError:
        pass
        
    l.addWidget(cal)
    
    bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    bbox.accepted.connect(dialog.accept)
    bbox.rejected.connect(dialog.reject)
    l.addWidget(bbox)
    
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return cal.selectedDate().toString("dd.MM.yyyy")
    return None

# ==============================================================================
# НИЖЕ ВСТАВЛЯЙ ВСЕ КЛАССЫ ДИАЛОГОВ ИЗ TaskTimer.py
# ==============================================================================
class DateRangeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор периода выгрузки")
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout(self)
        
        # Блок с начальной датой
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("С:"))
        self.start_date = QDateEdit(self)
        self.start_date.setCalendarPopup(True) # Включаем выпадающий календарь
        # По умолчанию ставим дату на месяц назад
        self.start_date.setDate(QDate.currentDate().addMonths(-1)) 
        start_layout.addWidget(self.start_date)
        layout.addLayout(start_layout)
        
        # Блок с конечной датой
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("По:"))
        self.end_date = QDateEdit(self)
        self.end_date.setCalendarPopup(True)
        # По умолчанию ставим сегодняшний день
        self.end_date.setDate(QDate.currentDate()) 
        end_layout.addWidget(self.end_date)
        layout.addLayout(end_layout)
        
        # Кнопки подтверждения и отмены
        btn_layout = QHBoxLayout()
        self.btn_export = QPushButton("Выгрузить")
        self.btn_cancel = QPushButton("Отмена")
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        # Привязываем кнопки к закрытию окна
        self.btn_export.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
    def get_dates(self):
        # Возвращаем даты в формате базы данных (например, ГГГГ-ММ-ДД)
        return self.start_date.date().toString("yyyy-MM-dd"), self.end_date.date().toString("yyyy-MM-dd")

class CustomToast(QDialog):
    # Добавили параметр is_modern=False
    def __init__(self, task_info, theme_palette, is_modern=False, on_click_callback=None, parent=None):
        super().__init__(parent)
        self.is_modern = is_modern
        self.on_click_callback = on_click_callback
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(420, 180)
        self.theme_palette = theme_palette
        self.setup_ui(task_info)
        self.position_widget()
        
        self.setWindowOpacity(0.0)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(400)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.start()
        
        QTimer.singleShot(15 * 60 * 1000, self.reject)

    def setup_ui(self, task_info):
        self.main_frame = QFrame(self)
        self.main_frame.setGeometry(10, 10, self.width() - 20, self.height() - 20)
        
        pal = self.theme_palette
        
        # === ДИНАМИЧЕСКИЙ ДИЗАЙН ===
        if self.is_modern:
            # СОВРЕМЕННЫЙ: плоский, скругленный, залитый фон
            self.main_frame.setStyleSheet(f"""
                QFrame {{ background-color: {pal['menu_bg']}; border: 2px solid {pal['expired']}; border-radius: 12px; }}
                QLabel {{ color: {pal['menu_fg']}; border: none; background: transparent; }}
                QPushButton {{ background-color: {pal['cal_comp_bg']}; color: {pal['menu_fg']}; border: 1px solid {pal['version']}; border-radius: 8px; padding: 8px; font-weight: bold; font-family: 'Segoe UI'; }}
                QPushButton:hover {{ background-color: {pal['menu_sel']}; border-color: {pal['in_progress']}; color: {pal['in_progress']}; }}
            """)
        else:
            # КЛАССИКА: эффект полупрозрачного затемненного стекла
            bg_hex = pal['menu_bg']
            try:
                # Извлекаем RGB для прозрачности (rgba)
                r, g, b = tuple(int(bg_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                bg_rgba = f"rgba({r}, {g}, {b}, 0.9)"
            except:
                bg_rgba = "rgba(30, 30, 30, 0.9)"
                
            self.main_frame.setStyleSheet(f"""
                QFrame {{ background-color: {bg_rgba}; border: 1px solid {pal['expired']}; border-radius: 8px; }}
                QLabel {{ color: {pal['menu_fg']}; border: none; background: transparent; }}
                QPushButton {{ background-color: rgba(255, 255, 255, 0.1); color: {pal['menu_fg']}; border: none; border-radius: 6px; padding: 8px; font-weight: bold; font-family: 'Segoe UI'; }}
                QPushButton:hover {{ background-color: rgba(255, 255, 255, 0.2); border: 1px solid {pal['in_progress']}; }}
            """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15); shadow.setColor(QColor(0, 0, 0, 180)); shadow.setOffset(0, 4)
        self.main_frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.main_frame); layout.setContentsMargins(15, 15, 15, 15)
        
        header = QLabel("⚠️ ВРЕМЯ ВЫШЛО!")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold)); header.setStyleSheet(f"color: {pal['expired']};")
        layout.addWidget(header)
        
        msg_label = QLabel(task_info); msg_label.setFont(QFont("Segoe UI", 11)); msg_label.setWordWrap(True)
        layout.addWidget(msg_label, stretch=1)
        
        btn_layout = QHBoxLayout()
        btn_work = QPushButton("▶ В работу"); btn_work.clicked.connect(lambda: self.handle_action(1))
        btn_1hour = QPushButton("⏳ +1 час"); btn_1hour.clicked.connect(lambda: self.handle_action(4))
        btn_reschedule = QPushButton("Перенести"); btn_reschedule.clicked.connect(lambda: self.handle_action(3))
        btn_close = QPushButton("Закрыть звук"); btn_close.clicked.connect(lambda: self.handle_action(0))
        
        for btn in (btn_work, btn_1hour, btn_reschedule, btn_close): btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

    def handle_action(self, result_code):
        if self.on_click_callback: self.on_click_callback()
        self.close_with_result(result_code)

    def position_widget(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        self.move(screen_geo.x() + screen_geo.width() - self.width() - 15, screen_geo.y() + screen_geo.height() - self.height() - 15)

    def close_with_result(self, result_code):
        self.anim.setDirection(QPropertyAnimation.Direction.Backward)
        self.anim.finished.connect(self.reject if result_code == 0 else lambda: self.done(result_code))
        self.anim.start()
        
    def showEvent(self, event): super().showEvent(event); self.raise_(); self.activateWindow()

class TemplateEditDialog(QDialog):
    def __init__(self, parent=None, template_data=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка шаблона")
        self.resize(400, 250)
        self.setFont(QFont("Segoe UI", 11))
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например: Быстрая правка")
        
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Текст задачи по умолчанию")
        
        self.hours_input = QLineEdit()
        self.hours_input.setPlaceholderText("Например: 1.5 (часа)")
        
        self.color_input = QComboBox()
        self.colors_map = {"Без цвета": "", "🔴 Красный": "#e74c3c", "🟠 Оранжевый": "#f39c12", "🟢 Зеленый": "#2ecc71", "🔵 Синий": "#3498db", "🟣 Фиолетовый": "#9b59b6"}
        for name, hex_val in self.colors_map.items():
            self.color_input.addItem(name, hex_val)
            
        if template_data:
            self.name_input.setText(template_data[1])
            self.task_input.setText(template_data[2])
            self.hours_input.setText(str(template_data[3]))
            idx = self.color_input.findData(template_data[4])
            if idx >= 0: self.color_input.setCurrentIndex(idx)
            
        layout.addRow("Название шаблона:", self.name_input)
        layout.addRow("Суть задачи:", self.task_input)
        layout.addRow("Сколько часов займет:", self.hours_input)
        layout.addRow("Цвет тега:", self.color_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
    def get_data(self):
        try: hours = float(self.hours_input.text().replace(',', '.'))
        except ValueError: hours = 1.0
        return (self.name_input.text().strip(), self.task_input.text().strip(), hours, self.color_input.currentData())

class TemplateManagerDialog(QDialog):
    def __init__(self, get_templates_cb, parent=None): # Заменили db_manager на функцию
        super().__init__(parent)
        self.setWindowTitle("Управление шаблонами")
        self.resize(400, 300)
        self.setFont(QFont("Segoe UI", 11))
        self.get_templates_cb = get_templates_cb
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Изменить")
        self.btn_del = QPushButton("Удалить")
        
        for btn in (self.btn_add, self.btn_edit, self.btn_del):
            btn.setMinimumHeight(35)
            btn_layout.addWidget(btn)
            
        layout.addLayout(btn_layout)
        
        self.btn_add.clicked.connect(self.add_template)
        self.btn_edit.clicked.connect(self.edit_template)
        self.btn_del.clicked.connect(self.del_template)
        
        events.templates_changed.connect(self.load_templates)
        self.load_templates()
    
    def load_templates(self):
        current_data = self.template_combo.currentData()
        self.template_combo.clear()
        self.template_combo.addItem("Без шаблона", None)
        if getattr(self, 'get_templates_cb', None):
            for row in self.get_templates_cb(): # <--- Вызываем функцию напрямую
                self.template_combo.addItem(row[1], row)
                
    def add_template(self):
        dlg = TemplateEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, task_text, hours, color = dlg.get_data()
            if name: events.action_add_template.emit(name, task_text, hours, color)
            
    def edit_template(self):
        item = self.list_widget.currentItem()
        if not item: return
        row_data = item.data(Qt.ItemDataRole.UserRole)
        dlg = TemplateEditDialog(self, row_data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, task_text, hours, color = dlg.get_data()
            if name: events.action_edit_template.emit(row_data[0], name, task_text, hours, color)
            
    def del_template(self):
        item = self.list_widget.currentItem()
        if not item: return
        if QMessageBox.question(self, "Удаление", "Удалить этот шаблон?") == QMessageBox.StandardButton.Yes:
            events.action_delete_template.emit(item.data(Qt.ItemDataRole.UserRole)[0])

# --- ОКНО СОЗДАНИЯ ЗАДАЧИ ---
from PyQt6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, 
                             QWidget, QLineEdit, QComboBox, QPushButton, 
                             QDialogButtonBox, QListWidget, QListWidgetItem, QLabel)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
from datetime import datetime, timedelta, timezone

class BaseTaskDialog(QDialog):
    def __init__(self, parent=None, title="Новый контракт", tz_offset=3, get_templates_cb=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(480, 520)
        self.setFont(QFont("Segoe UI", 11))
        self.tz_offset = tz_offset
        self.get_templates_cb = get_templates_cb
        self.start_immediately = False

    def init_common_widgets(self, layout):
        """Создает и настраивает все элементы управления, которые общи для обоих окон"""
        # --- ШАБЛОНЫ ---
        template_layout = QHBoxLayout()
        template_layout.setContentsMargins(0, 0, 0, 0)
        self.template_combo = QComboBox()
        self.btn_manage_templates = QPushButton("⚙️")
        self.btn_manage_templates.setFixedWidth(40)
        self.btn_manage_templates.setProperty("iconButton", "true")
        self.btn_manage_templates.clicked.connect(self.open_template_manager)
        
        template_layout.addWidget(self.template_combo)
        template_layout.addWidget(self.btn_manage_templates)
        
        tw = QWidget()
        tw.setLayout(template_layout)
        layout.addRow("Шаблон:", tw)
        
        # --- БАЗОВЫЕ ПОЛЯ ---
        self.client_input, self.task_input = QLineEdit(), QLineEdit()
        self.client_input.setPlaceholderText("Введите имя клиента")
        self.task_input.setPlaceholderText("Опишите задачу")
        
        # --- ДАТА ---
        self.date_layout = QHBoxLayout()
        self.date_layout.setContentsMargins(0, 0, 0, 0)
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("ДД.ММ.ГГГГ")
        self.date_input.setText(QDate.currentDate().toString("dd.MM.yyyy"))
        
        self.btn_calendar = QPushButton("📅")
        self.btn_calendar.setFixedWidth(40)
        self.btn_calendar.setProperty("iconButton", "true")
        self.btn_calendar.clicked.connect(self.pick_date)
        
        self.date_layout.addWidget(self.date_input)
        self.date_layout.addWidget(self.btn_calendar)
        
        date_widget = QWidget()
        date_widget.setLayout(self.date_layout)
        
        # --- ВРЕМЯ ---
        self.time_input = QComboBox()
        self.time_input.setEditable(True)
        self.time_input.lineEdit().setPlaceholderText("ЧЧ:ММ")
        for h in range(0, 24):
            self.time_input.addItem(f"{h:02d}:00")
            self.time_input.addItem(f"{h:02d}:30")
            
        current_tz = timezone(timedelta(hours=self.tz_offset))
        self.time_input.setCurrentText((datetime.now(current_tz) + timedelta(hours=1)).strftime("%H:%M"))
        
        # --- ЦВЕТ ---
        self.color_input = QComboBox()
        self.colors_map = get_tag_colors()
        for name, hex_val in self.colors_map.items():
            self.color_input.addItem(name, hex_val)
            
        layout.addRow("Клиент:", self.client_input)
        layout.addRow("Суть задачи:", self.task_input)
        layout.addRow("Дедлайн (дата):", date_widget)
        layout.addRow("Дедлайн (время):", self.time_input)
        layout.addRow("Цвет тега:", self.color_input)
        
        # --- ЧЕК-ЛИСТ (ПОДЗАДАЧИ) ---
        subtask_container = QWidget()
        subtask_layout = QVBoxLayout(subtask_container)
        subtask_layout.setContentsMargins(0, 0, 0, 0)
        subtask_layout.setSpacing(6)
        
        self.subtasks_list = QListWidget()
        self.subtasks_list.setMaximumHeight(90)
        self.subtasks_list.keyPressEvent = self.handle_list_keys
        
        sub_input_layout = QHBoxLayout()
        sub_input_layout.setContentsMargins(0, 0, 0, 0)
        self.subtask_input = QLineEdit()
        self.subtask_input.setPlaceholderText("Добавить шаг плана...")
        self.subtask_input.returnPressed.connect(self.add_subtask_from_dialog)
        
        self.btn_add_subtask = QPushButton("➕")
        self.btn_add_subtask.setFixedWidth(40)
        self.btn_add_subtask.setProperty("iconButton", "true")
        self.btn_add_subtask.clicked.connect(self.add_subtask_from_dialog)
        
        sub_input_layout.addWidget(self.subtask_input)
        sub_input_layout.addWidget(self.btn_add_subtask)
        
        subtask_layout.addWidget(self.subtasks_list)
        subtask_layout.addLayout(sub_input_layout)
        
        layout.addRow("План:", subtask_container)

        # --- КНОПКИ ---
        buttons_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Создать")
        self.btn_ok.setObjectName("primaryBtn") 
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.validate_and_accept)
        
        self.btn_quick = QPushButton("▶ Создать и начать")
        self.btn_quick.clicked.connect(self.quick_start_accept)
        
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_ok)
        buttons_layout.addWidget(self.btn_quick)
        buttons_layout.addWidget(self.btn_cancel)
        
        layout.addRow(buttons_layout)

        self.load_templates()
        self.template_combo.currentIndexChanged.connect(self.apply_template)
        
        self.client_input.returnPressed.connect(self.validate_and_accept)
        self.task_input.returnPressed.connect(self.validate_and_accept)
    
    def set_task_data(self, task):
        """Заполняет поля диалога данными из объекта существующей задачи для редактирования"""
        try:
            # Устанавливаем название/заголовок задачи
            if hasattr(self, 'task_name_input'):
                self.task_name_input.setText(getattr(task, 'task_name', getattr(task, 'title', '')))
            elif hasattr(self, 'title_input'):
                self.title_input.setText(getattr(task, 'title', getattr(task, 'task_name', '')))

            # Устанавливаем клиента
            if hasattr(self, 'client_input'):
                self.client_input.setText(getattr(task, 'client_name', getattr(task, 'client', '')))

            # Устанавливаем дату и время, если они есть в задаче
            if hasattr(task, 'deadline') and task.deadline:
                if hasattr(self, 'date_input'):
                    self.date_input.setText(task.deadline.strftime("%d.%m.%Y"))
                if hasattr(self, 'time_input'):
                    self.time_input.setCurrentText(task.deadline.strftime("%H:%M"))
        except Exception as e:
            print(f"Ошибка при загрузке данных в TaskDialog: {e}")

    # --- ОСТАЛЬНЫЕ МЕТОДЫ БЕЗ ИЗМЕНЕНИЙ ---
    def pick_date(self):
        new_date = select_date_via_calendar(self, self.date_input.text())
        if new_date:
            self.date_input.setText(new_date)

    def load_templates(self):
        current_data = self.template_combo.currentData()
        self.template_combo.clear()
        self.template_combo.addItem("Без шаблона", None)
        if getattr(self, 'get_templates_cb', None):
            for row in self.get_templates_cb(): # <--- Вызываем функцию напрямую
                self.template_combo.addItem(row[1], row)

    def apply_template(self, index):
        row = self.template_combo.currentData()
        if row:
            self.task_input.setText(row[2])
            color_idx = self.color_input.findData(row[4])
            if color_idx >= 0:
                self.color_input.setCurrentIndex(color_idx)

    def add_subtask_from_dialog(self):
        text = self.subtask_input.text().strip()
        if text:
            item = QListWidgetItem(f"⚪ {text}")
            item.setData(Qt.ItemDataRole.UserRole, text)
            self.subtasks_list.addItem(item)
            self.subtask_input.clear()

    def handle_list_keys(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in self.subtasks_list.selectedItems():
                self.subtasks_list.takeItem(self.subtasks_list.row(item))
        else:
            QListWidget.keyPressEvent(self.subtasks_list, event)

    def get_subtasks_list(self):
        subtasks = []
        for i in range(self.subtasks_list.count()):
            text = self.subtasks_list.item(i).data(Qt.ItemDataRole.UserRole)
            if text:
                subtasks.append({"text": text, "done": False})
        return subtasks
    
    def open_template_manager(self):
        from tabs.dialogs import TemplateManagerDialog
        dlg = TemplateManagerDialog(self, self.get_templates_cb)
        dlg.exec()
        self.load_templates()

    def quick_start_accept(self):
        self.start_immediately = True
        self.validate_and_accept()

    def validate_and_accept(self):
        try:
            # Безопасно достаем текст из инпута редактируемого комбобокса
            time_str = self.time_input.lineEdit().text() if self.time_input.isEditable() else self.time_input.currentText()
            
            parsed_d, parsed_t = smart_parse_datetime(self.date_input.text(), time_str, self.tz_offset)
            self.date_input.setText(parsed_d)
            self.time_input.setCurrentText(parsed_t)
        except Exception:
            pass 
        self.accept()
        
    def get_task_data(self):
        color = self.color_input.currentData() or ""
        
        # Надежно извлекаем текст времени с учетом ручного ввода (например, "1300")
        if self.time_input.isEditable() and self.time_input.lineEdit():
            raw_time = self.time_input.lineEdit().text().strip()
        else:
            raw_time = self.time_input.currentText().strip()
            
        # Прогоняем через умный парсер, чтобы формат всегда был "ЧЧ:ММ" и дата корректной
        d_val = self.date_input.text().strip()
        try:
            parsed_d, parsed_t = smart_parse_datetime(d_val, raw_time, self.tz_offset)
        except Exception as e:
            print(f"2. Ошибка парсера: {e}\n-----") # И ЭТУ
            parsed_d, parsed_t = d_val, raw_time

        return {
            "client": self.client_input.text().strip(),
            "task": self.task_input.text().strip(),
            "date": parsed_d,
            "time": parsed_t,
            "color": color,
            "subtasks": self.get_subtasks_list(),
            "start_immediately": self.start_immediately
        }

class ClassicTaskDialog(BaseTaskDialog):
    def __init__(self, parent=None, title="Новый контракт", tz_offset=3, get_templates_cb=None, theme_key=None):
        super().__init__(parent, title, tz_offset, get_templates_cb)
        
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.init_common_widgets(layout)
        
class ModernTaskDialog(BaseTaskDialog):
    def __init__(self, parent=None, title="Новый контракт", tz_offset=3, get_templates_cb=None, theme_key='dark_fantasy'):
        super().__init__(parent, title, tz_offset, get_templates_cb)
        
        # Современные отступы чуть шире для «воздуха»
        layout = QFormLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(24, 24, 24, 24)
        
        self.init_common_widgets(layout)
        
        # Автоматически применяем переданную тему оформления
        self.apply_modern_styling(theme_key)

    def apply_modern_styling(self, theme_key):
        from tabs.themes import get_theme_palette
        pal = get_theme_palette(theme_key)
        
        bg_main = pal['menu_bg']
        bg_input = pal['history_bg']
        accent = pal['in_progress']
        fg_text = pal['menu_fg']
        border_col = pal['version']
        hover_bg = pal['menu_sel']

        self.setStyleSheet(f"""
            QDialog {{ 
                background-color: {bg_main}; 
                border-radius: 16px; 
                border: 1px solid {accent};
            }}
            
            QLabel {{ 
                color: {fg_text}; 
                font-family: 'Segoe UI'; 
                font-size: 12px; 
                font-weight: 600; 
                background: transparent; 
            }}
            
            QLineEdit, QComboBox, QDateEdit, QTimeEdit, QListWidget {{
                background-color: {bg_input}; 
                color: {fg_text}; 
                border: 1px solid {border_col};
                border-radius: 8px; 
                padding: 8px 12px; 
                font-family: 'Segoe UI'; 
                font-size: 13px;
            }}
            
            QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QTimeEdit:hover {{
                border: 1px solid {fg_text};
            }}
            
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus {{ 
                border: 2px solid {accent}; 
                background-color: rgba(255, 255, 255, 0.02);
            }}
            
            QListWidget::item {{ 
                padding: 6px; 
                border-bottom: 1px solid {border_col}; 
                border-radius: 4px;
            }}
            
            /* Основные кнопки */
            QPushButton {{
                background-color: {hover_bg}; 
                color: {fg_text}; 
                border: 1px solid {border_col};
                border-radius: 8px; 
                padding: 10px 18px; 
                font-family: 'Segoe UI'; 
                font-size: 13px; 
                font-weight: bold;
            }}
            
            QPushButton:hover {{ 
                background-color: {accent}; 
                border: 1px solid {accent}; 
                color: #ffffff; 
            }}
            
            /* Стили для маленьких кнопок с иконками (⚙️, 📅, ➕) */
            QPushButton[iconButton="true"] {{
                background-color: {bg_input};
                border: 1px solid {border_col};
                border-radius: 8px;
                font-size: 15px;
                padding: 0px;
            }}
            QPushButton[iconButton="true"]:hover {{
                background-color: {hover_bg};
                border: 1px solid {accent};
                color: {fg_text};
            }}
            
            /* Главная кнопка создания */
            QPushButton#primaryBtn {{ 
                background-color: {accent}; 
                color: #ffffff; 
                border: none; 
            }}
            QPushButton#primaryBtn:hover {{ 
                background-color: {fg_text}; 
                color: {bg_main}; 
            }}
        """)



class RescheduleDialog(QDialog):
    def __init__(self, parent=None, current_date="", current_time="", tz_offset=3):
        super().__init__(parent)
        self.setWindowTitle("Перенос задачи")
        self.resize(350, 220)
        self.setFont(QFont("Segoe UI", 11))
        self.tz_offset = tz_offset

        # Сохраняем исходные значения задачи для правильного расчета быстрых кнопок
        self.base_date_str = current_date or QDate.currentDate().toString("dd.MM.yyyy")
        
        current_tz = timezone(timedelta(hours=self.tz_offset))
        if current_time:
            self.base_time_str = current_time
        else:
            self.base_time_str = (datetime.now(current_tz) + timedelta(hours=1)).strftime("%H:%M")

        layout = QFormLayout(self)

        # --- ДАТА ---
        self.date_layout = QHBoxLayout()
        self.date_layout.setContentsMargins(0, 0, 0, 0)
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("ДД.ММ.ГГГГ")
        self.date_input.setText(self.base_date_str)

        self.btn_calendar = QPushButton("📅")
        self.btn_calendar.setFixedWidth(40)
        self.btn_calendar.clicked.connect(self.pick_date)

        self.date_layout.addWidget(self.date_input)
        self.date_layout.addWidget(self.btn_calendar)

        date_widget = QWidget()
        date_widget.setLayout(self.date_layout)

        # --- ВРЕМЯ ---
        self.time_input = QComboBox()
        self.time_input.setEditable(True)
        self.time_input.lineEdit().setPlaceholderText("ЧЧ:ММ")
        for h in range(0, 24):
            self.time_input.addItem(f"{h:02d}:00")
            self.time_input.addItem(f"{h:02d}:30")
            
        self.time_input.setCurrentText(self.base_time_str)

        layout.addRow("Новая дата:", date_widget)
        layout.addRow("Новое время:", self.time_input)

        # --- БЫСТРЫЕ КНОПКИ ПЕРЕНОСА ---
        quick_layout = QHBoxLayout()
        self.btn_1h = QPushButton("На 1 час")
        self.btn_tomorrow = QPushButton("На завтра")
        self.btn_3d = QPushButton("На 3 дня")
        self.btn_week = QPushButton("На неделю")

        for btn in [self.btn_1h, self.btn_tomorrow, self.btn_3d, self.btn_week]:
            quick_layout.addWidget(btn)

        quick_widget = QWidget()
        quick_widget.setLayout(quick_layout)
        layout.addRow(quick_widget)

        # Подключаем быстрые кнопки (отталкиваемся от исходных даты/времени задачи)
        self.btn_1h.clicked.connect(lambda: self.shift_datetime(hours=1))
        self.btn_tomorrow.clicked.connect(lambda: self.shift_datetime(days=1))
        self.btn_3d.clicked.connect(lambda: self.shift_datetime(days=3))
        self.btn_week.clicked.connect(lambda: self.shift_datetime(days=7))

        # --- ОК / CANCEL ---
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def pick_date(self):
        new_date = select_date_via_calendar(self, self.date_input.text())
        if new_date:
            self.date_input.setText(new_date)

    def shift_datetime(self, hours=0, days=0):
        try:
            # Собираем базовый объект datetime из исходных данных задачи
            base_dt = datetime.strptime(f"{self.base_date_str} {self.base_time_str}", "%d.%m.%Y %H:%M")
            
            # Прибавляем нужный интервал
            new_dt = base_dt + timedelta(hours=hours, days=days)
            
            # Обновляем поля в интерфейсе
            self.date_input.setText(new_dt.strftime("%d.%m.%Y"))
            self.time_input.setCurrentText(new_dt.strftime("%H:%M"))
        except Exception:
            pass

    def validate_and_accept(self):
        try:
            time_str = self.time_input.lineEdit().text() if self.time_input.isEditable() else self.time_input.currentText()
            parsed_d, parsed_t = smart_parse_datetime(self.date_input.text(), time_str, self.tz_offset)
            self.date_input.setText(parsed_d)
            self.time_input.setCurrentText(parsed_t)
        except Exception:
            pass 
        self.accept()

    def get_new_datetime(self):
        time_str = self.time_input.lineEdit().text() if self.time_input.isEditable() else self.time_input.currentText()
        return {
            "date": self.date_input.text().strip(),
            "time": time_str.strip()
        }
class BugReportDialog(QDialog):
    def __init__(self, parent=None, app_version="v1.0"):
        super().__init__(parent)
        self.setWindowTitle("Сообщить об ошибке")
        self.resize(500, 400)
        self.setFont(QFont("Segoe UI", 11))
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel("Опиши, что случилось и как повторить ошибку:")
        layout.addWidget(info_label)
        
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Например: Я нажал на кнопку переноса задачи, и программа вылетела...")
        layout.addWidget(self.desc_input)
        
        sys_info_label = QLabel("Техническая информация (прикрепится автоматически):")
        layout.addWidget(sys_info_label)
        
        self.sys_info = QTextBrowser()
        self.sys_info.setMaximumHeight(80)
        sys_text = f"Версия TaskTimer: {app_version}\n"
        sys_text += f"Система: {platform.system()} {platform.release()} ({platform.version()})\n"
        sys_text += f"Архитектура: {platform.machine()}"
        self.sys_info.setPlainText(sys_text)
        layout.addWidget(self.sys_info)
        
        btn_layout = QHBoxLayout()
        self.btn_github = QPushButton("Создать баг-репорт на GitHub")
        self.btn_github.setMinimumHeight(40)
        self.btn_github.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        self.btn_github.clicked.connect(self.open_github)
        
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_github)
        layout.addLayout(btn_layout)

    def open_github(self):
        user_desc = self.desc_input.toPlainText().strip()
        sys_info = self.sys_info.toPlainText()
        
        issue_body = f"**Описание проблемы:**\n{user_desc if user_desc else 'Без описания'}\n\n"
        issue_body += f"**Системная информация:**\n```text\n{sys_info}\n```"
        
        QApplication.clipboard().setText(issue_body)
        QMessageBox.information(self, "Подготовка", "Мы скопировали текст ошибки в буфер обмена.\n\nСейчас откроется страница GitHub. Просто нажми Ctrl+V в поле описания (Leave a comment) и сохрани.")
        
        # --- СТАЛО: Вызов через константу ---
        webbrowser.open(GITHUB_ISSUES_URL)
        self.accept()
