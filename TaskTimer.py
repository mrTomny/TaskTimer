import sys
import json
import os
import shutil
import calendar
import winsound
import ctypes
import re
import csv
import urllib.request
import subprocess
from datetime import datetime, timezone, timedelta

from PyQt6.QtWidgets import (QApplication, QMainWindow, QDockWidget, 
                             QListWidget, QListWidgetItem, QCalendarWidget, QLabel, 
                             QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QPushButton, QDialog, QFormLayout, 
                             QLineEdit, QDialogButtonBox, QMessageBox, 
                             QMenu, QTextEdit, QFrame, QComboBox, QFileDialog, QCheckBox,
                             QSystemTrayIcon, QSplitter)
from PyQt6.QtCore import Qt, QTimer, QDate, QTime, QRect, QPoint
from PyQt6.QtGui import (QFont, QTextCharFormat, QColor, QPainter, QPen, QPixmap, 
                         QIcon, QShortcut, QKeySequence, QAction, QPdfWriter, QPageSize, QTextDocument)

# --- Виджет скриншота ---
class SnippingWidget(QWidget):
    def __init__(self, client_name, on_capture_callback):
        super().__init__()
        self.client_name = client_name
        self.on_capture_callback = on_capture_callback
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        
        geometry = QRect()
        for screen in QApplication.screens():
            geometry = geometry.united(screen.geometry())
        self.setGeometry(geometry)
        
        self.original_pixmap = QPixmap(geometry.size())
        painter = QPainter(self.original_pixmap)
        for screen in QApplication.screens():
            screenshot = screen.grabWindow(0)
            offset = screen.geometry().topLeft() - geometry.topLeft()
            painter.drawPixmap(offset, screenshot)
        painter.end()
        
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.begin = QPoint()
        self.end = QPoint()
        self.is_drawing = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.original_pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        
        if self.is_drawing:
            rect = QRect(self.begin, self.end).normalized()
            painter.drawPixmap(rect, self.original_pixmap.copy(rect))
            pen = QPen(QColor("#d4af37"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = self.begin
        self.is_drawing = True
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.is_drawing = False
        rect = QRect(self.begin, self.end).normalized()
        self.hide()
        
        file_path_saved = None
        if rect.width() > 10 and rect.height() > 10:
            capture = self.original_pixmap.copy(rect)
            safe_name = re.sub(r'[\\/*?:"<>|]', "", self.client_name).strip()
            default_path = f"{safe_name}.png" if safe_name else "Скриншот.png"
            
            file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить скриншот", default_path, "Images (*.png *.jpg)")
            if file_path:
                capture.save(file_path)
                file_path_saved = file_path
        
        if self.on_capture_callback:
            self.on_capture_callback(file_path_saved)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.on_capture_callback:
                self.on_capture_callback(None)
            self.close()

# --- Всплывающее окно при срабатывании таймера ---
class TimerActionDialog(QDialog):
    def __init__(self, task_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Время вышло!")
        self.resize(350, 160)
        self.setFont(QFont("Segoe UI", 11))
        
        layout = QVBoxLayout(self)
        msg_label = QLabel(f"<b>Задача требует внимания:</b><br>{task_info}")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        
        btn_work = QPushButton("▶ Взять в работу")
        btn_work.clicked.connect(lambda: self.done(1))
        
        btn_reschedule = QPushButton("Перенести вручную")
        btn_reschedule.clicked.connect(lambda: self.done(3))
        
        btn_close = QPushButton("Просто закрыть звук")
        btn_close.clicked.connect(self.reject)
        
        for btn in (btn_work, btn_reschedule, btn_close):
            btn.setMinimumHeight(35)
            layout.addWidget(btn)

# --- Диалоговое окно для задач ---
class TaskDialog(QDialog):
    def __init__(self, parent=None, title="Новый контракт", tz_offset=3):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(400, 250)
        self.setFont(QFont("Segoe UI", 11))
        
        layout = QFormLayout(self)
        
        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("Введите имя клиента")
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Опишите задачу")
        
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("ДД.ММ.ГГГГ")
        self.date_input.setText(QDate.currentDate().toString("dd.MM.yyyy"))
        
        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("ЧЧ:ММ")
        current_tz = timezone(timedelta(hours=tz_offset))
        default_time = datetime.now(current_tz) + timedelta(hours=1)
        self.time_input.setText(default_time.strftime("%H:%M"))
        
        layout.addRow("Клиент:", self.client_input)
        layout.addRow("Суть задачи:", self.task_input)
        layout.addRow("Дедлайн (дата):", self.date_input)
        layout.addRow("Дедлайн (время):", self.time_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def validate_and_accept(self):
        try:
            datetime.strptime(f"{self.date_input.text().strip()} {self.time_input.text().strip()}", "%d.%m.%Y %H:%M")
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Ошибка ввода", "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ и время в формате ЧЧ:ММ")

    def get_task_data(self):
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        return {
            "client": self.client_input.text().strip(),
            "task": self.task_input.text().strip(),
            "date": self.date_input.text().strip(),
            "time": self.time_input.text().strip(),
            "status": "Ожидание",
            "notes": "",
            "history": [f"[{current_time}] Задача создана"]
        }

    def set_task_data(self, data):
        self.client_input.setText(data.get("client", ""))
        self.task_input.setText(data.get("task", ""))
        self.date_input.setText(data.get("date", ""))
        self.time_input.setText(data.get("time", ""))

class RescheduleDialog(QDialog):
    def __init__(self, parent=None, current_date_str="", current_time_str=""):
        super().__init__(parent)
        self.setWindowTitle("Перенос контракта")
        self.resize(350, 200)
        self.setFont(QFont("Segoe UI", 11))
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("ДД.ММ.ГГГГ")
        if current_date_str: self.date_input.setText(current_date_str)
            
        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("ЧЧ:ММ")
        if current_time_str: self.time_input.setText(current_time_str)
            
        form_layout.addRow("Новая дата:", self.date_input)
        form_layout.addRow("Новое время:", self.time_input)
        layout.addLayout(form_layout)
        
        quick_layout = QHBoxLayout()
        btn_tomorrow = QPushButton("На завтра")
        btn_3days = QPushButton("На 3 дня")
        btn_week = QPushButton("На неделю")
        
        btn_tomorrow.clicked.connect(lambda: self.add_days_to_date(1))
        btn_3days.clicked.connect(lambda: self.add_days_to_date(3))
        btn_week.clicked.connect(lambda: self.add_days_to_date(7))
        
        quick_layout.addWidget(btn_tomorrow)
        quick_layout.addWidget(btn_3days)
        quick_layout.addWidget(btn_week)
        layout.addLayout(quick_layout)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
    def add_days_to_date(self, days):
        new_date = QDate.currentDate().addDays(days)
        self.date_input.setText(new_date.toString("dd.MM.yyyy"))

    def validate_and_accept(self):
        try:
            datetime.strptime(f"{self.date_input.text().strip()} {self.time_input.text().strip()}", "%d.%m.%Y %H:%M")
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Ошибка ввода", "Формат даты: ДД.ММ.ГГГГ, время: ЧЧ:ММ")

    def get_new_datetime(self):
        return {
            "date": self.date_input.text().strip(),
            "time": self.time_input.text().strip()
        }

# --- Основное окно приложения ---
class GuildDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Таймер: Вкладочная архитектура")
        self.resize(1600, 900) 
        
        # --- ТЕКУЩАЯ ВЕРСИЯ ПРОГРАММЫ ---
        self.current_version = "v0.9" 
        
        self.app_dir = os.path.join(os.getenv('APPDATA'), 'TaskTimer')
        os.makedirs(self.app_dir, exist_ok=True)
        
        self.data_file = os.path.join(self.app_dir, "tasks.json")
        self.settings_file = os.path.join(self.app_dir, "settings.json")
        
        self.highlighted_dates = []
        self.tz_offset = 3
        self.sound_type = "system"
        self.sound_path = ""
        self.show_exit_warning = True
        self.is_testing_sound = False 
        self.force_quit = False
        
        self.migrate_old_data()
        self.create_backup()
        
        self.setup_tray_icon()
        self.setup_hotkeys()
        
        self.load_settings() 
        self.apply_dark_fantasy_style()
        
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Segoe UI", 12))
        self.setCentralWidget(self.tabs)
        
        # --- 1. Вкладка: Досье контракта ---
        self.tab_main = QWidget()
        main_layout = QVBoxLayout(self.tab_main)
        
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_layout = QVBoxLayout(info_frame)
        
        self.lbl_client = QLabel("Клиент: не выбран")
        self.lbl_client.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_task = QLabel("Задача: ...")
        self.lbl_task.setFont(QFont("Segoe UI", 14))
        self.lbl_deadline = QLabel("Дедлайн: ...")
        self.lbl_deadline.setFont(QFont("Segoe UI", 14))
        
        info_layout.addWidget(self.lbl_client)
        info_layout.addWidget(self.lbl_task)
        info_layout.addWidget(self.lbl_deadline)
        main_layout.addWidget(info_frame)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        notes_widget = QWidget()
        notes_layout = QVBoxLayout(notes_widget)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.addWidget(QLabel("Заметки:"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setFont(QFont("Segoe UI", 12))
        self.notes_edit.setPlaceholderText("Выберите контракт слева...")
        self.notes_edit.setEnabled(False) 
        self.notes_edit.textChanged.connect(self.auto_save_notes)
        notes_layout.addWidget(self.notes_edit)
        
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.addWidget(QLabel("История изменений:"))
        self.history_edit = QTextEdit()
        self.history_edit.setFont(QFont("Segoe UI", 11))
        self.history_edit.setReadOnly(True)
        self.history_edit.setStyleSheet("background-color: #141414; color: #8c7b65;")
        history_layout.addWidget(self.history_edit)
        
        splitter.addWidget(notes_widget)
        splitter.addWidget(history_widget)
        
        main_layout.addWidget(splitter)
        
        buttons_layout = QHBoxLayout()
        self.btn_in_progress = QPushButton("▶ Взять в работу")
        self.btn_success = QPushButton("Успешно (Перенос)")
        self.btn_reschedule = QPushButton("Перенести вручную")
        self.btn_screenshot = QPushButton("📸 Скриншот (Ctrl+S)") 
        self.btn_complete = QPushButton("Завершить (В историю)")
        
        for btn in (self.btn_in_progress, self.btn_success, self.btn_reschedule, self.btn_screenshot, self.btn_complete):
            btn.setFont(QFont("Segoe UI", 12))
            btn.setMinimumHeight(40)
            btn.setEnabled(False)
            buttons_layout.addWidget(btn)
        
        self.btn_in_progress.clicked.connect(self.start_work)
        self.btn_success.clicked.connect(self.mark_success)
        self.btn_reschedule.clicked.connect(self.reschedule_task)
        self.btn_screenshot.clicked.connect(self.trigger_screenshot)
        self.btn_complete.clicked.connect(self.complete_task)
        
        main_layout.addLayout(buttons_layout)
        self.tabs.addTab(self.tab_main, "Досье контракта")
        
        # --- 2. Вкладка: Календарь ---
        self.tab_calendar = QWidget()
        cal_layout = QHBoxLayout(self.tab_calendar)
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setFont(QFont("Segoe UI", 12))
        self.calendar.selectionChanged.connect(self.show_tasks_for_selected_date)
        
        self.day_tasks_list = QListWidget()
        self.day_tasks_list.setFont(QFont("Segoe UI", 12))
        self.day_tasks_list.setMinimumWidth(400)
        self.day_tasks_list.itemClicked.connect(self.load_task_from_calendar)
        
        cal_layout.addWidget(self.calendar, stretch=2)
        cal_layout.addWidget(self.day_tasks_list, stretch=1)
        self.tabs.addTab(self.tab_calendar, "Календарь")
        
        # --- 3. Вкладка Настройки ---
        self.tab_settings = QWidget()
        settings_layout = QFormLayout(self.tab_settings)
        settings_layout.setSpacing(20)
        settings_layout.setContentsMargins(30, 30, 30, 30)
        
        tz_names = {
            -12: "Острова Бейкер и Хауленд", -11: "Мидуэй, Паго-Паго", -10: "Гавайи, Гонолулу",
            -9: "Аляска", -8: "Лос-Анджелес, Ванкувер", -7: "Денвер, Солт-Лейк-Сити",
            -6: "Мехико, Чикаго", -5: "Нью-Йорк, Торонто", -4: "Каракас, Ла-Пас",
            -3: "Буэнос-Айрес, Сан-Паулу", -2: "Южная Георгия", -1: "Азорские острова",
            0: "Лондон, Лиссабон", 1: "Париж, Берлин, Рим", 2: "Калининград, Хельсинки, Киев",
            3: "Москва, Минск, Стамбул", 4: "Самара, Баку, Дубай", 5: "Екатеринбург, Ташкент",
            6: "Омск, Алматы", 7: "Красноярск, Бангкок", 8: "Иркутск, Пекин",
            9: "Якутск, Токио", 10: "Владивосток, Сидней", 11: "Магадан, Сахалин",
            12: "Камчатка, Окленд", 13: "Самоа, Тонга", 14: "Острова Лайн"
        }

        self.combo_tz = QComboBox()
        self.combo_tz.setFont(QFont("Segoe UI", 12))
        for i in range(-12, 15):
            sign = "+" if i > 0 else ""
            city = f" ({tz_names.get(i, '')})" if i in tz_names else ""
            self.combo_tz.addItem(f"UTC{sign}{i}:00{city}", i)
            if i == self.tz_offset:
                self.combo_tz.setCurrentIndex(self.combo_tz.count() - 1)
        self.combo_tz.currentIndexChanged.connect(self.save_settings)
        
        self.combo_sound = QComboBox()
        self.combo_sound.setFont(QFont("Segoe UI", 12))
        self.combo_sound.addItem("Системный звук (Beep)", "system")
        self.combo_sound.addItem("Свой аудиофайл (.wav, .mp3)", "custom") 
        if self.sound_type == "custom":
            self.combo_sound.setCurrentIndex(1)
        self.combo_sound.currentIndexChanged.connect(self.on_sound_type_changed)
        
        file_layout = QHBoxLayout()
        self.line_sound_path = QLineEdit(self.sound_path)
        self.line_sound_path.setEnabled(self.sound_type == "custom")
        self.btn_browse_sound = QPushButton("Обзор...")
        self.btn_browse_sound.setEnabled(self.sound_type == "custom")
        self.btn_browse_sound.clicked.connect(self.browse_sound_file)
        self.btn_test_sound = QPushButton("Тест звука")
        self.btn_test_sound.clicked.connect(self.toggle_test_sound) 
        
        file_layout.addWidget(self.line_sound_path)
        file_layout.addWidget(self.btn_browse_sound)
        file_layout.addWidget(self.btn_test_sound)
        
        self.cb_exit_warning = QCheckBox("Показывать предупреждение при закрытии программы, если есть незаконченные задачи")
        self.cb_exit_warning.setFont(QFont("Segoe UI", 11))
        self.cb_exit_warning.setChecked(self.show_exit_warning)
        self.cb_exit_warning.stateChanged.connect(self.on_warning_cb_changed)
        
        self.btn_export = QPushButton("Выгрузить отчеты (CSV, Excel, PDF)")
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_export.clicked.connect(self.export_tasks)
        
        self.btn_check_update = QPushButton("Проверить обновления")
        self.btn_check_update.setMinimumHeight(40)
        self.btn_check_update.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_check_update.clicked.connect(self.check_for_updates)
        
        settings_layout.addRow(QLabel("Часовой пояс:"), self.combo_tz)
        settings_layout.addRow(QLabel("Тип оповещения:"), self.combo_sound)
        settings_layout.addRow(QLabel("Файл звука:"), file_layout)
        settings_layout.addRow("", self.cb_exit_warning)
        settings_layout.addRow(QLabel("Экспорт:"), self.btn_export)
        settings_layout.addRow(QLabel("Обновления:"), self.btn_check_update)
        
        self.tabs.addTab(self.tab_settings, "Настройки")
        
        # --- Боковая панель ---
        self.task_dock = QDockWidget("Оперативная сводка", self)
        self.task_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        task_container = QWidget()
        task_layout = QVBoxLayout(task_container)
        
        self.clock_label = QLabel("00:00:00")
        self.clock_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock_label.setStyleSheet("color: #d4af37; padding: 10px;") 
        task_layout.addWidget(self.clock_label)
        
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.textChanged.connect(self.refresh_task_list_ui)
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["По дедлайну", "По алфавиту", "По статусу"])
        self.sort_combo.currentIndexChanged.connect(self.refresh_task_list_ui)
        
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(self.sort_combo)
        task_layout.addLayout(filter_layout)
        
        self.task_list = QListWidget()
        self.task_list.setFont(QFont("Segoe UI", 11))
        self.task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self.show_context_menu)
        self.task_list.itemClicked.connect(self.load_task_to_center)
        task_layout.addWidget(self.task_list)
        
        self.add_btn = QPushButton("Добавить контракт (Ctrl+N)")
        self.add_btn.clicked.connect(self.add_task)
        task_layout.addWidget(self.add_btn)
        
        self.task_dock.setWidget(task_container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.task_dock)
        
        self.tasks_data = []
        
        self.load_tasks() 
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
        self.update_clock() 

    # --- Механизм обновлений ---
    def check_for_updates(self):
        self.btn_check_update.setText("Проверка...")
        self.btn_check_update.setEnabled(False)
        QApplication.processEvents() 
        
        api_url = "https://api.github.com/repos/mrTomny/TaskTimer/releases/latest"
        
        try:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'TaskTimer-App'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                
                latest_version = data.get("tag_name")
                
                if latest_version and latest_version != self.current_version:
                    download_url = None
                    for asset in data.get("assets", []):
                        if asset.get("name", "").endswith(".exe"):
                            download_url = asset.get("browser_download_url")
                            break
                            
                    if download_url:
                        self.prompt_update(latest_version, download_url)
                    else:
                        QMessageBox.information(self, "Обновление", f"Релиз {latest_version} найден, но внутри нет .exe файла.")
                else:
                    QMessageBox.information(self, "Обновление", "У вас установлена самая последняя версия!")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось проверить обновления.\n{e}")
        finally:
            self.btn_check_update.setText("Проверить обновления")
            self.btn_check_update.setEnabled(True)

    def prompt_update(self, latest_version, download_url):
        reply = QMessageBox.question(
            self, 'Доступно обновление!', 
            f'Вышла новая версия: {latest_version}\nТекущая: {self.current_version}\n\nХотите скачать и установить её прямо сейчас?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.perform_update(download_url)

    def perform_update(self, download_url):
        self.btn_check_update.setText("Скачивание...")
        QApplication.processEvents()
        
        current_exe_path = sys.executable 
        new_exe_path = os.path.join(self.app_dir, "TaskTimer_new.exe")
        bat_path = os.path.join(self.app_dir, "updater.bat")
        
        try:
            urllib.request.urlretrieve(download_url, new_exe_path)
            
            bat_content = f"""@echo off
chcp 65001
echo Установка обновления... Пожалуйста, подождите.
timeout /t 3 /nobreak > NUL
move /y "{new_exe_path}" "{current_exe_path}"
start "" "{current_exe_path}"
del "%~f0"
"""
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
                
            subprocess.Popen([bat_path], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            self.force_quit = True
            QApplication.quit()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка обновления", f"Произошла ошибка при скачивании или установке:\n{e}")
            self.btn_check_update.setText("Проверить обновления")

    # --- Миграция и Бэкапы ---
    def migrate_old_data(self):
        old_data = "tasks.json"
        old_settings = "settings.json"
        
        if os.path.exists(old_data) and not os.path.exists(self.data_file):
            try:
                shutil.copy2(old_data, self.data_file)
                os.rename(old_data, old_data + ".old")
            except Exception: pass
            
        if os.path.exists(old_settings) and not os.path.exists(self.settings_file):
            try:
                shutil.copy2(old_settings, self.settings_file)
                os.rename(old_settings, old_settings + ".old")
            except Exception: pass

    def create_backup(self):
        if os.path.exists(self.data_file):
            today_str = datetime.now().strftime('%Y%m%d')
            backup_file = os.path.join(self.app_dir, f"tasks_backup_{today_str}.json")
            if not os.path.exists(backup_file):
                try:
                    shutil.copy2(self.data_file, backup_file)
                except Exception: pass

    # --- Настройка системного трея ---
    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        icon_pixmap = QPixmap(32, 32)
        icon_pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(icon_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#d4af37"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        
        self.tray_icon.setIcon(QIcon(icon_pixmap))
        self.tray_icon.setToolTip("Таймер задач")
        
        tray_menu = QMenu()
        restore_action = tray_menu.addAction("Развернуть")
        restore_action.triggered.connect(self.restore_window)
        quit_action = tray_menu.addAction("Выход")
        quit_action.triggered.connect(self.quit_app)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.restore_window()

    def restore_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def quit_app(self):
        self.force_quit = True
        QApplication.quit()

    # --- Горячие клавиши ---
    def setup_hotkeys(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.add_task)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.trigger_screenshot)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.quit_app)

    # --- Обработка закрытия окна ---
    def closeEvent(self, event):
        if self.force_quit:
            event.accept()
            return
            
        if self.show_exit_warning:
            has_pending = False
            for data in self.tasks_data:
                if data.get("status") != "Завершено":
                    has_pending = True
                    break
                    
            if has_pending:
                msg = QMessageBox(self)
                msg.setWindowTitle("Выход")
                msg.setText("У вас остались незавершенные задачи.\n\nСвернуть программу в трей (рядом с часами) или закрыть полностью?")
                
                btn_tray = msg.addButton("В трей", QMessageBox.ButtonRole.ActionRole)
                btn_quit = msg.addButton("Закрыть полностью", QMessageBox.ButtonRole.DestructiveRole)
                btn_cancel = msg.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
                
                cb = QCheckBox("Больше не показывать это предупреждение")
                msg.setCheckBox(cb)
                
                msg.exec()
                
                if cb.isChecked():
                    self.show_exit_warning = False
                    self.cb_exit_warning.setChecked(False)
                    self.save_settings()
                    
                if msg.clickedButton() == btn_quit:
                    self.force_quit = True
                    QApplication.quit() 
                    event.accept()
                elif msg.clickedButton() == btn_tray:
                    self.hide()
                    self.tray_icon.showMessage("Таймер", "Программа работает в фоновом режиме", QSystemTrayIcon.MessageIcon.Information, 2000)
                    event.ignore()
                else:
                    event.ignore()
                return

        self.hide()
        self.tray_icon.showMessage("Таймер", "Программа свернута в трей", QSystemTrayIcon.MessageIcon.Information, 2000)
        event.ignore()

    def on_warning_cb_changed(self, state):
        self.show_exit_warning = (state == 2)
        self.save_settings()

    # --- Подсистема Звука ---
    def play_sound(self, loop=False):
        if self.sound_type == "custom" and os.path.exists(self.sound_path):
            if self.sound_path.lower().endswith(".mp3"):
                ctypes.windll.winmm.mciSendStringW("close CustomAlert", None, 0, None)
                ctypes.windll.winmm.mciSendStringW(f'open "{self.sound_path}" alias CustomAlert', None, 0, None)
                if loop:
                    ctypes.windll.winmm.mciSendStringW("play CustomAlert repeat", None, 0, None)
                else:
                    ctypes.windll.winmm.mciSendStringW("play CustomAlert", None, 0, None)
            else:
                flags = winsound.SND_FILENAME | winsound.SND_ASYNC
                if loop: flags |= winsound.SND_LOOP
                winsound.PlaySound(self.sound_path, flags)
        else:
            QApplication.beep()

    def stop_sound(self):
        ctypes.windll.winmm.mciSendStringW("stop CustomAlert", None, 0, None)
        ctypes.windll.winmm.mciSendStringW("close CustomAlert", None, 0, None)
        try: winsound.PlaySound(None, winsound.SND_PURGE)
        except: pass

    def toggle_test_sound(self):
        if self.is_testing_sound:
            self.stop_sound()
            self.is_testing_sound = False
            self.btn_test_sound.setText("Тест звука")
            self.btn_test_sound.setStyleSheet("") 
        else:
            self.play_sound(loop=True)
            self.is_testing_sound = True
            self.btn_test_sound.setText("⏹ Остановить тест")
            self.btn_test_sound.setStyleSheet("background-color: #7a1f1f; color: #ffffff; border-color: #a32a2a;")

    # --- Скриншотер ---
    def trigger_screenshot(self):
        selected_items = self.task_list.selectedItems()
        if not selected_items: return
        item = selected_items[0]
        data = item.data(Qt.ItemDataRole.UserRole)
        client_name = data.get("client", "Клиент")
        
        self.hide()
        self.snipper = SnippingWidget(client_name, self.on_screenshot_captured)
        self.snipper.show()

    def on_screenshot_captured(self, file_path):
        self.show()
        if not file_path: return 
        selected_items = self.task_list.selectedItems()
        if not selected_items: return
        
        item = selected_items[0]
        data = item.data(Qt.ItemDataRole.UserRole)
        
        new_note = f"\n[Скриншот-отчет: {file_path}]"
        notes = self.notes_edit.toPlainText()
        if notes: self.notes_edit.setPlainText(notes + new_note)
        else: self.notes_edit.setPlainText(new_note.strip())
        
        self.add_history_log(data, "Прикреплен скриншот")
        item.setData(Qt.ItemDataRole.UserRole, data)
        self.save_tasks()

    # --- Настройки и Выгрузка ---
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.tz_offset = data.get("tz_offset", 3)
                    self.sound_type = data.get("sound_type", "system")
                    self.sound_path = data.get("sound_path", "")
                    self.show_exit_warning = data.get("show_exit_warning", True)
            except Exception:
                pass

    def save_settings(self):
        self.tz_offset = self.combo_tz.currentData()
        self.sound_type = self.combo_sound.currentData()
        self.sound_path = self.line_sound_path.text()
        
        data = {
            "tz_offset": self.tz_offset, 
            "sound_type": self.sound_type, 
            "sound_path": self.sound_path,
            "show_exit_warning": self.show_exit_warning
        }
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def on_sound_type_changed(self):
        is_custom = (self.combo_sound.currentData() == "custom")
        self.line_sound_path.setEnabled(is_custom)
        self.btn_browse_sound.setEnabled(is_custom)
        self.save_settings()

    def browse_sound_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выберите аудиофайл", "", "Аудио (*.wav *.mp3)")
        if file_name:
            self.line_sound_path.setText(file_name)
            self.save_settings()

    def export_tasks(self):
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Сохранить отчет", "Отчет_по_задачам", 
            "CSV Files (*.csv);;Excel Files (*.xlsx);;PDF Document (*.pdf)"
        )
        if not file_path: return
        
        try:
            if selected_filter.startswith("CSV"):
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f: 
                    writer = csv.writer(f, delimiter=';')
                    writer.writerow(["Статус", "Клиент", "Задача", "Дедлайн", "История изменений"])
                    for data in self.tasks_data:
                        history_str = " | ".join(data.get('history', []))
                        writer.writerow([data.get('status'), data.get('client'), data.get('task'), f"{data.get('date')} {data.get('time')}", history_str])
            
            elif selected_filter.startswith("Excel"):
                try:
                    import openpyxl
                except ImportError:
                    QMessageBox.warning(self, "Требуется модуль", "Для экспорта в Excel необходимо установить библиотеку openpyxl.\n\nОткройте консоль и введите:\npip install openpyxl")
                    return
                
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Контракты"
                ws.append(["Статус", "Клиент", "Задача", "Дедлайн", "История изменений"])
                
                for data in self.tasks_data:
                    history_str = " | ".join(data.get('history', []))
                    ws.append([data.get('status'), data.get('client'), data.get('task'), f"{data.get('date')} {data.get('time')}", history_str])
                
                wb.save(file_path)
            
            elif selected_filter.startswith("PDF"):
                writer = QPdfWriter(file_path)
                writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
                writer.setResolution(300)
                
                doc = QTextDocument()
                html = "<h1 style='color: #2b2b2b; font-family: sans-serif;'>Отчет по контрактам</h1>"
                html += "<table border='1' cellspacing='0' cellpadding='8' width='100%' style='border-collapse: collapse; font-family: sans-serif;'>"
                html += "<tr style='background-color: #f2f2f2;'><th>Статус</th><th>Клиент</th><th>Задача</th><th>Дедлайн</th><th>История</th></tr>"
                
                for data in self.tasks_data:
                    history_str = "<br>".join(data.get('history', []))
                    html += f"<tr><td>{data.get('status')}</td><td>{data.get('client')}</td><td>{data.get('task')}</td><td>{data.get('date')} {data.get('time')}</td><td><small>{history_str}</small></td></tr>"
                
                html += "</table>"
                doc.setHtml(html)
                doc.print(writer)

            QMessageBox.information(self, "Готово", "Отчет успешно выгружен!")
            
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить файл:\n{str(e)}")

    # --- Логика Данных ---
    def refresh_task_list_ui(self):
        selected_data = None
        if self.task_list.selectedItems():
            selected_data = self.task_list.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
            
        self.task_list.clear()
        
        search_text = self.search_input.text().lower()
        sort_type = self.sort_combo.currentText()
        
        display_list = list(self.tasks_data)
        
        if sort_type == "По дедлайну":
            display_list.sort(key=lambda x: self.safe_str_to_datetime(x.get('date'), x.get('time')))
        elif sort_type == "По алфавиту":
            display_list.sort(key=lambda x: x.get('client', '').lower())
        elif sort_type == "По статусу":
            display_list.sort(key=lambda x: x.get('status', ''))

        for data in display_list:
            item = QListWidgetItem(self.format_task_string(data))
            item.setData(Qt.ItemDataRole.UserRole, data)
            
            if search_text:
                if search_text not in data.get('client', '').lower() and search_text not in data.get('task', '').lower():
                    item.setHidden(True)
            
            if data.get("status") == "Завершено":
                item.setHidden(True)
                
            self.task_list.addItem(item)
            
            if selected_data and data.get('client') == selected_data.get('client') and data.get('task') == selected_data.get('task') and data.get('date') == selected_data.get('date'):
                item.setSelected(True)

    def safe_str_to_datetime(self, date_str, time_str):
        try:
            return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        except:
            return datetime.max

    def update_calendar_formats(self):
        for d in self.highlighted_dates:
            self.calendar.setDateTextFormat(d, QTextCharFormat())
        self.highlighted_dates.clear()
        
        fmt_active = QTextCharFormat()
        fmt_active.setBackground(QColor("#4a1c1c"))
        fmt_active.setForeground(QColor("#d4af37"))
        fmt_active.setFontWeight(QFont.Weight.Bold)
        
        fmt_completed = QTextCharFormat()
        fmt_completed.setBackground(QColor("#2c3e50")) 
        fmt_completed.setForeground(QColor("#8c7b65"))
        
        active_dates = set()
        completed_dates = set()

        for data in self.tasks_data:
            date_str = data.get("date")
            if date_str:
                if data.get("status") == "Завершено": completed_dates.add(date_str)
                else: active_dates.add(date_str)
                    
        for d_str in active_dates:
            qdate = QDate.fromString(d_str, "dd.MM.yyyy")
            self.calendar.setDateTextFormat(qdate, fmt_active)
            self.highlighted_dates.append(qdate)
            
        for d_str in completed_dates:
            if d_str not in active_dates: 
                qdate = QDate.fromString(d_str, "dd.MM.yyyy")
                self.calendar.setDateTextFormat(qdate, fmt_completed)
                self.highlighted_dates.append(qdate)
        
        self.show_tasks_for_selected_date()

    def show_tasks_for_selected_date(self):
        self.day_tasks_list.clear()
        selected_date = self.calendar.selectedDate().toString("dd.MM.yyyy")
        
        tasks_found = False
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data.get("date") == selected_date:
                status = data.get("status", "Ожидание")
                display_text = f"[{status}] {data.get('time')} - {data.get('client')}\nЗадача: {data.get('task')}"
                day_item = QListWidgetItem(display_text)
                day_item.setData(Qt.ItemDataRole.UserRole, item) 
                
                if status == "Завершено": day_item.setForeground(QColor("#8c7b65"))
                self.day_tasks_list.addItem(day_item)
                tasks_found = True
                
        if not tasks_found:
            self.day_tasks_list.addItem("На этот день задач нет.")

    def load_task_from_calendar(self, day_item):
        main_item = day_item.data(Qt.ItemDataRole.UserRole)
        if main_item:
            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)
                if data.get('client') == main_item.get('client') and data.get('task') == main_item.get('task'):
                    item.setSelected(True)
                    self.load_task_to_center(item)
                    self.tabs.setCurrentIndex(0) 
                    break

    def load_task_to_center(self, item):
        self.notes_edit.blockSignals(True)
        data = item.data(Qt.ItemDataRole.UserRole)
        self.lbl_client.setText(f"Клиент: {data.get('client', '')}")
        self.lbl_task.setText(f"Задача: {data.get('task', '')}")
        self.lbl_deadline.setText(f"Дедлайн: {data.get('date', '')} в {data.get('time', '')} [{data.get('status', '')}]")
        self.notes_edit.setPlainText(data.get("notes", ""))
        self.notes_edit.setEnabled(True)
        
        history_text = "\n".join(data.get("history", []))
        self.history_edit.setPlainText(history_text)
        
        status = data.get("status")
        self.btn_in_progress.setEnabled(status in ("Ожидание", "Время вышло"))
        self.btn_success.setEnabled(status == "В работе")
        self.btn_reschedule.setEnabled(status != "Завершено")
        self.btn_screenshot.setEnabled(status != "Завершено") 
        self.btn_complete.setEnabled(status != "Завершено") 
        
        self.notes_edit.blockSignals(False)

    def refresh_central_panel(self):
        selected_items = self.task_list.selectedItems()
        if selected_items: self.load_task_to_center(selected_items[0])
        else: self.clear_central_panel()

    def clear_central_panel(self):
        self.lbl_client.setText("Клиент: не выбран")
        self.lbl_task.setText("Задача: ...")
        self.lbl_deadline.setText("Дедлайн: ...")
        
        self.notes_edit.blockSignals(True)
        self.notes_edit.clear()
        self.notes_edit.setEnabled(False)
        self.notes_edit.blockSignals(False)
        
        self.history_edit.clear()
        
        self.btn_in_progress.setEnabled(False)
        self.btn_success.setEnabled(False)
        self.btn_reschedule.setEnabled(False)
        self.btn_screenshot.setEnabled(False)
        self.btn_complete.setEnabled(False)

    def auto_save_notes(self):
        selected_items = self.task_list.selectedItems()
        if not selected_items: return
        item = selected_items[0]
        data = item.data(Qt.ItemDataRole.UserRole)
        data["notes"] = self.notes_edit.toPlainText()
        item.setData(Qt.ItemDataRole.UserRole, data)
        self.save_tasks()

    def save_tasks(self):
        new_data_list = []
        for i in range(self.task_list.count()):
            new_data_list.append(self.task_list.item(i).data(Qt.ItemDataRole.UserRole))
            
        for data in self.tasks_data:
            if data not in new_data_list:
                new_data_list.append(data)
                
        self.tasks_data = new_data_list
        
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.tasks_data, f, ensure_ascii=False, indent=4)
        except: pass
        self.update_calendar_formats() 

    def load_tasks(self):
        self.tasks_data = []
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.tasks_data = json.load(f)
            except: pass
            
        for data in self.tasks_data:
            if "notes" not in data: data["notes"] = ""
            if "history" not in data: data["history"] = []
            
        self.refresh_task_list_ui()
        self.update_calendar_formats()

    def add_history_log(self, data, message):
        if "history" not in data:
            data["history"] = []
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        data["history"].append(f"[{current_time}] {message}")

    def update_clock(self):
        current_tz = timezone(timedelta(hours=self.tz_offset))
        current_time = datetime.now(current_tz)
        self.clock_label.setText(current_time.strftime("%H:%M:%S"))
        
        status_changed = False 
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            
            if data.get("status") == "Завершено": continue
                
            if data.get("status", "Ожидание") == "Ожидание":
                try:
                    task_dt = datetime.strptime(f"{data['date']} {data['time']}", "%d.%m.%Y %H:%M")
                    task_dt = task_dt.replace(tzinfo=current_tz)
                    
                    if current_time >= task_dt:
                        data["status"] = "Время вышло" 
                        self.add_history_log(data, "Сработал таймер")
                        item.setData(Qt.ItemDataRole.UserRole, data)
                        item.setText(self.format_task_string(data)) 
                        status_changed = True 
                        self.play_sound(loop=True)
                        self.handle_timer_expired(item, data)
                    else:
                        time_diff = task_dt - current_time
                        total_sec = int(time_diff.total_seconds())
                        hours, rem = divmod(total_sec, 3600)
                        mins, secs = divmod(rem, 60)
                        
                        if time_diff.days > 0: countdown = f"-{time_diff.days}д {hours:02d}:{mins:02d}:{secs:02d}"
                        else: countdown = f"-{hours:02d}:{mins:02d}:{secs:02d}"
                        item.setText(self.format_task_string(data, countdown))
                except ValueError: pass
                    
        if status_changed:
            self.save_tasks()
            self.refresh_central_panel() 
            self.show_tasks_for_selected_date() 

    def handle_timer_expired(self, item, data):
        self.restore_window()
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.show()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()
        self.activateWindow()
        self.raise_()
        
        self.task_list.setCurrentItem(item)
        info_str = f"Клиент: {data.get('client')}\nЧто нужно: {data.get('task')}"
        
        dialog = TimerActionDialog(info_str, self)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        result = dialog.exec()
        
        if result == 1: self.start_work()
        elif result == 3: self.reschedule_task()
        else: self.stop_sound()

    def format_task_string(self, data, countdown_str=""):
        status = data.get("status", "Ожидание")
        timer_display = f" [{countdown_str}]" if countdown_str else ""
        return f"{status}{timer_display} | {data['client']} | {data['task']} | {data['date']} {data['time']}"

    def add_task(self):
        dialog = TaskDialog(self, title="Новый контракт", tz_offset=self.tz_offset)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_task_data()
            if data["client"].strip() or data["task"].strip():
                self.tasks_data.append(data)
                self.refresh_task_list_ui()
                self.save_tasks()
                self.update_clock()

    def show_context_menu(self, position):
        item = self.task_list.itemAt(position)
        if not item: return 
        item.setSelected(True)
        self.load_task_to_center(item) 
        
        data = item.data(Qt.ItemDataRole.UserRole)
        current_status = data.get("status", "Ожидание")
        
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #d4af37; border: 1px solid #d4af37; font-size: 14px; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #3b3b3b; }
        """)
        
        start_action = success_action = reschedule_action = complete_action = None
        
        if current_status in ("Ожидание", "Время вышло"):
            start_action = menu.addAction("Взять в работу")
            complete_action = menu.addAction("Завершить (В историю)")
            menu.addSeparator()
        elif current_status == "В работе":
            success_action = menu.addAction("Успешно (Перенос на месяц)")
            reschedule_action = menu.addAction("Перенести вручную")
            complete_action = menu.addAction("Завершить (В историю)")
            menu.addSeparator()
            
        edit_action = menu.addAction("Редактировать") 
        delete_action = menu.addAction("Удалить")
        
        action = menu.exec(self.task_list.mapToGlobal(position))
        
        if start_action and action == start_action: self.start_work()
        elif success_action and action == success_action: self.mark_success()
        elif reschedule_action and action == reschedule_action: self.reschedule_task()
        elif complete_action and action == complete_action: self.complete_task()
        elif action == edit_action: self.edit_task()
        elif action == delete_action: self.delete_task()

    # --- Жизненный цикл задач ---
    def start_work(self):
        self.stop_sound() 
        selected_items = self.task_list.selectedItems()
        if not selected_items: return
        item = selected_items[0]
        data = item.data(Qt.ItemDataRole.UserRole)
        data['status'] = "В работе"
        self.add_history_log(data, "Взято в работу")
        item.setData(Qt.ItemDataRole.UserRole, data)
        item.setText(self.format_task_string(data))
        self.save_tasks()
        self.refresh_central_panel()

    def mark_success(self):
        self.stop_sound()
        selected_items = self.task_list.selectedItems()
        if not selected_items: return
        item = selected_items[0]
        data = item.data(Qt.ItemDataRole.UserRole)

        try: current_date = datetime.strptime(data['date'], "%d.%m.%Y")
        except ValueError: current_date = datetime.now()
        
        month = current_date.month - 1 + 1
        year = current_date.year + month // 12
        month = month % 12 + 1
        day = min(current_date.day, calendar.monthrange(year, month)[1])
        new_date = current_date.replace(year=year, month=month, day=day)
        
        if new_date.weekday() == 5: new_date -= timedelta(days=1)
        elif new_date.weekday() == 6: new_date -= timedelta(days=2)
            
        old_date_str = data['date']
        data['date'] = new_date.strftime("%d.%m.%Y")
        data['status'] = "Ожидание"
        
        self.add_history_log(data, f"Успешное выполнение. Перенос с {old_date_str} на {data['date']}")
        
        item.setData(Qt.ItemDataRole.UserRole, data)
        self.save_tasks()
        self.update_clock() 
        self.refresh_central_panel() 

    def complete_task(self):
        self.stop_sound()
        selected_items = self.task_list.selectedItems()
        if not selected_items: return
        item = selected_items[0]
        data = item.data(Qt.ItemDataRole.UserRole)
        data['status'] = "Завершено"
        self.add_history_log(data, "Задача завершена")
        item.setData(Qt.ItemDataRole.UserRole, data)
        item.setText(self.format_task_string(data))
        self.save_tasks()
        self.refresh_task_list_ui()
        self.clear_central_panel()

    def reschedule_task(self):
        self.stop_sound()
        selected_items = self.task_list.selectedItems()
        if not selected_items: return
        item = selected_items[0]
        data = item.data(Qt.ItemDataRole.UserRole)
        
        dialog = RescheduleDialog(self, data['date'], data['time'])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_dt = dialog.get_new_datetime()
            old_dt_str = f"{data['date']} {data['time']}"
            data['date'] = new_dt['date']
            data['time'] = new_dt['time']
            data['status'] = "Ожидание"
            
            self.add_history_log(data, f"Перенос дедлайна вручную: с {old_dt_str} на {data['date']} {data['time']}")
            
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.save_tasks()
            self.refresh_task_list_ui()
            self.update_clock()
            self.refresh_central_panel() 

    def edit_task(self):
        self.stop_sound()
        selected_items = self.task_list.selectedItems()
        if not selected_items: return 
        item = selected_items[0]
        current_data = item.data(Qt.ItemDataRole.UserRole)
        
        dialog = TaskDialog(self, title="Редактирование", tz_offset=self.tz_offset)
        dialog.set_task_data(current_data) 
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_task_data()
            new_data["status"] = current_data.get("status", "Ожидание")
            new_data["notes"] = current_data.get("notes", "")
            new_data["history"] = current_data.get("history", [])
            
            try:
                old_dt = datetime.strptime(f"{current_data['date']} {current_data['time']}", "%d.%m.%Y %H:%M")
                new_dt = datetime.strptime(f"{new_data['date']} {new_data['time']}", "%d.%m.%Y %H:%M")
                if new_dt > old_dt:
                    new_data["status"] = "Ожидание"
            except ValueError:
                pass
            
            if new_data["client"].strip() or new_data["task"].strip():
                self.add_history_log(new_data, "Отредактированы данные контракта")
                item.setData(Qt.ItemDataRole.UserRole, new_data)
                
                for i, t in enumerate(self.tasks_data):
                    if t == current_data:
                        self.tasks_data[i] = new_data
                        break
                        
                self.save_tasks() 
                self.refresh_task_list_ui()
                self.update_clock() 
                self.refresh_central_panel()

    def delete_task(self):
        self.stop_sound()
        selected_items = self.task_list.selectedItems()
        if not selected_items: return
        item = selected_items[0]
        data = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(self, 'Отмена', 'Точно удалить?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            if data in self.tasks_data:
                self.tasks_data.remove(data)
            self.task_list.takeItem(self.task_list.row(item))
            self.save_tasks() 
            self.clear_central_panel() 

    def apply_dark_fantasy_style(self):
        dark_style = """
        QMainWindow, QDialog, QWidget { background-color: #1a1a1a; color: #d3c6a6; }
        QComboBox { background-color: #0d0d0d; border: 2px solid #4a3c31; border-radius: 5px; padding: 8px; }
        QComboBox:focus { border: 2px solid #d4af37; background-color: #141414; }
        QTabWidget::pane { border: 2px solid #4a3c31; background-color: #1a1a1a; border-radius: 5px; }
        QTabBar::tab { background-color: #2b2b2b; color: #8c7b65; padding: 10px 30px; border: 2px solid #4a3c31; border-bottom: none; border-top-left-radius: 5px; border-top-right-radius: 5px; margin-right: 2px; }
        QTabBar::tab:selected { background-color: #1a1a1a; color: #d4af37; border-color: #d4af37; }
        QListWidget { background-color: #242424; border: 2px solid #4a3c31; border-radius: 5px; padding: 5px; outline: none; }
        QListWidget::item { padding: 12px; border-bottom: 1px solid #333333; }
        QListWidget::item:selected { background-color: #3b2f2f; color: #d4af37; border: 1px solid #7a1f1f; }
        QPushButton { background-color: #332922; border: 2px solid #5c4a3d; border-radius: 5px; padding: 8px; font-weight: bold; }
        QPushButton:hover { background-color: #4a3c31; border-color: #d4af37; color: #ffffff; }
        QPushButton:disabled { background-color: #1a1a1a; color: #4d4d4d; border-color: #333333; }
        QLineEdit, QTextEdit { background-color: #0d0d0d; border: 2px solid #4a3c31; border-radius: 5px; padding: 8px; }
        QLineEdit:focus, QTextEdit:focus { border: 2px solid #d4af37; }
        """
        self.setStyleSheet(dark_style)

if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    
    app.setQuitOnLastWindowClosed(False)
    
    app.setStyle("Fusion") 
    window = GuildDashboard()
    window.show()
    sys.exit(app.exec())