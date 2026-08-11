import os
import re
from datetime import datetime, timezone, timedelta
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSplitter, QListWidget, QListWidgetItem, QLineEdit, QTextBrowser,
    QCalendarWidget, QComboBox, QCheckBox, QFormLayout, QSlider, QFileDialog, 
    QDockWidget, QAbstractItemView, QTabWidget, QMenu, QApplication
)
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QCursor, QDesktopServices
from PyQt6.QtCore import Qt, QSize, QDate, QUrl

from tabs.notes import LinkableTextEdit, NotesManager
from tabs.archive import ArchiveTab
from tabs.settings import SettingsPanelWidget
from tabs.widgets import TaskDetailsWidget
from tabs.events import events
from tabs.themes import get_theme_palette, get_tag_colors
from tabs.utils import format_time_spent, calculate_dynamic_time, extract_spent_time_from_history, calculate_countdown_status
from tabs.services import TaskService
from tabs.dialogs import ClassicTaskDialog
from tabs.base_workspace import WorkspaceContract

# =========================================================================
# КАРТОЧКА КЛАССИЧЕСКОГО СПИСКА (Перенесена из TaskTimer.py)
# =========================================================================
class TaskCardWidget(QWidget):
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setFixedHeight(70)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setup_ui()

    def update_status_color(self):
        status_color = "#90A4AE"
        bg_style = "background-color: transparent; border-radius: 6px;"
        
        if self.task.status == "В работе": 
            status_color = "#2ecc71"
            bg_style = "background-color: rgba(46, 204, 113, 0.15); border: 1px solid rgba(46, 204, 113, 0.5); border-radius: 6px;"
        elif self.task.status in ("Выполнено", "Завершено"): 
            status_color = "#2ecc71"
        elif self.task.status == "Время вышло": 
            status_color = "#e74c3c"
            bg_style = "background-color: rgba(231, 76, 60, 0.2); border: 1px solid rgba(231, 76, 60, 0.6); border-radius: 6px;"
            
        if hasattr(self, 'status_label'):
            self.status_label.setStyleSheet(f"color: {status_color}; font-size: 11px; font-weight: bold; border: none; background: transparent;")
            self.status_label.setText(self.task.status)
        
        self.setStyleSheet(f"TaskCardWidget {{ {bg_style} }}")

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 7, 7, 7) 
        main_layout.setSpacing(10)

        self.color_strip = QFrame(self)
        self.color_strip.setFixedWidth(5)
        card_color = self.task.color if self.task.color else ""
        if card_color:
            self.color_strip.setStyleSheet(f"background-color: {card_color}; border-radius: 2px;")
            self.color_strip.setVisible(True)
        else:
            self.color_strip.setVisible(False)
            
        main_layout.addWidget(self.color_strip)

        left_layout = QVBoxLayout()
        left_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.countdown_label = QLabel("", self)
        self.countdown_label.setStyleSheet("background-color: #2C3E50; color: #4DB6AC; padding: 6px 10px; border-radius: 6px; font-weight: bold; font-size: 12px;")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setVisible(False) 
        left_layout.addWidget(self.countdown_label)
        main_layout.addLayout(left_layout)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        
        self.client_label = QLabel(self.task.client or "Без клиента", self)
        self.client_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.client_label.setStyleSheet("color: #FFFFFF; border: none; background: transparent;") 

        self.task_label = QLabel(self.task.task or "Нет описания", self)
        self.task_label.setFont(QFont("Segoe UI", 10))
        self.task_label.setStyleSheet("color: #B0BEC5; border: none; background: transparent;")
        self.task_label.setWordWrap(True)

        self.info_frame = QHBoxLayout()
        self.info_frame.setContentsMargins(0, 0, 0, 0)
        self.info_frame.setSpacing(10)

        deadline_str = self.task.deadline.strftime("%d.%m.%Y %H:%M") if hasattr(self.task, 'deadline') else "Нет дедлайна"
        self.deadline_label = QLabel(f"📅 {deadline_str}", self)
        self.deadline_label.setStyleSheet("color: #90A4AE; font-size: 11px; border: none; background: transparent;")
        self.status_label = QLabel(self.task.status, self)
        
        self.info_frame.addWidget(self.deadline_label)
        self.info_frame.addWidget(self.status_label)
        self.info_frame.addStretch() 

        content_layout.addWidget(self.client_label)
        content_layout.addWidget(self.task_label)
        content_layout.addLayout(self.info_frame)
        
        main_layout.addLayout(content_layout)
        main_layout.setStretchFactor(content_layout, 1)
        self.update_status_color()

    def update_countdown(self, text):
        if text:
            self.countdown_label.setText(text)
            self.countdown_label.setVisible(True)
        else:
            self.countdown_label.setVisible(False)

# =========================================================================
# ГЛАВНЫЙ КЛАСС КЛАССИЧЕСКОГО ИНТЕРФЕЙСА
# =========================================================================
class ClassicWorkspace(QMainWindow, WorkspaceContract):
    # Превращаем переменные в свойства, требуемые контрактом
    dialog_class = ClassicTaskDialog
    is_modern_style = False

    def __init__(self, task_repo, controller, main_window, parent=None):
        super().__init__(parent)
        # Удалите отсюда строки self.dialog_class = ... и self.is_modern_style = ...
        self.task_repo = task_repo
        self.controller = controller
        self.main_win = main_window # Ссылка на хост для глобальных вызовов (настройки, трей и т.д.)
        
        self.highlighted_dates = []
        
        # Настраиваем центральный виджет (Вкладки)
        self.tabs = QTabWidget(self)
        self.tabs.setFont(QFont("Segoe UI", 12))
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tabs)
        
        # Собираем интерфейс
        self.setup_classic_ui()
        
        # Подписываемся на события шины
        events.data_changed.connect(self.refresh_all_views)
        events.timer_tick.connect(self.update_timers_and_clock)
        
        # === ИСПРАВЛЕНИЕ БАГА 1: Грузим данные при старте ===
        self.refresh_all_views()

    # --- 1. СБОРКА ИНТЕРФЕЙСА ---
    def setup_classic_ui(self):
        self.setup_main_tab()
        self.setup_notes_tab()
        self.setup_calendar_tab()
        self.setup_analytics_tab()
        self.setup_archive_tab()
        self.setup_settings_tab()
        self.setup_dock()

    def setup_main_tab(self):
        self.tab_main = QWidget()
        main_layout = QVBoxLayout(self.tab_main)
        main_layout.setContentsMargins(0, 5, 5, 5) 
        main_layout.setSpacing(15)
        
        self.info_frame = QFrame()
        self.info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_layout = QVBoxLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        
        self.lbl_client = QLabel("👤 Клиент: не выбран")
        self.lbl_client.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_task = QLabel("📌 Задача: ...")
        self.lbl_task.setFont(QFont("Segoe UI", 14))
        self.lbl_deadline = QLabel("⏳ Дедлайн: ...")
        self.lbl_deadline.setFont(QFont("Segoe UI", 14))
        self.lbl_spent = QLabel("⌛ Потрачено: 0 мин")
        self.lbl_spent.setFont(QFont("Segoe UI", 12))
        self.lbl_spent.setStyleSheet("color: #3498db; font-weight: bold;")
        
        info_layout.addWidget(self.lbl_client)
        info_layout.addWidget(self.lbl_task)
        info_layout.addWidget(self.lbl_deadline)
        info_layout.addWidget(self.lbl_spent)
        main_layout.addWidget(self.info_frame)
        
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.task_details_widget = TaskDetailsWidget(self.splitter)
        
        history_widget, history_layout = QWidget(), QVBoxLayout()
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.addWidget(QLabel("История изменений:"))
        self.history_edit = QTextBrowser()
        self.history_edit.setFont(QFont("Segoe UI", 11))
        self.history_edit.setReadOnly(True)
        history_layout.addWidget(self.history_edit)
        history_widget.setLayout(history_layout)
        
        self.splitter.addWidget(self.task_details_widget)
        self.splitter.addWidget(history_widget)
        main_layout.addWidget(self.splitter)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12) 
        
        self.btn_in_progress = QPushButton("▶ В работу")
        self.btn_in_progress.setObjectName("primaryBtn")
        self.btn_in_progress.clicked.connect(lambda checked=False: events.action_start_work.emit(self.get_current_task()))
        
        self.btn_success = QPushButton("✅ Успешно")
        self.btn_success.clicked.connect(lambda checked=False: events.action_mark_success.emit(self.get_current_task()))
        
        self.btn_reschedule = QPushButton("📅 Перенести")
        self.btn_reschedule.clicked.connect(lambda checked=False: events.action_reschedule_task.emit(self.get_current_task()))
        
        self.btn_screenshot = QPushButton("📸 Скриншот")
        self.btn_screenshot.clicked.connect(lambda checked=False: events.action_screenshot.emit(self.get_current_task()))
        
        self.btn_complete = QPushButton("🏁 В архив")
        self.btn_complete.clicked.connect(lambda checked=False: events.action_complete_task.emit(self.get_current_task()))
        
        for btn in (self.btn_in_progress, self.btn_success, self.btn_reschedule, self.btn_screenshot, self.btn_complete):
            btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            btn.setMinimumHeight(45)
            btn.setEnabled(False)
            buttons_layout.addWidget(btn)
            
        main_layout.addLayout(buttons_layout)
        self.tabs.addTab(self.tab_main, "Рабочая область")
        
    def setup_notes_tab(self):
        self.tab_notes = QWidget()
        notes_layout = QVBoxLayout(self.tab_notes)
        self.notes_manager = NotesManager(self.controller.get_notes)
        notes_layout.addWidget(self.notes_manager)
        self.tabs.addTab(self.tab_notes, "Заметки")

    def setup_calendar_tab(self):
        self.tab_calendar = QWidget()
        cal_layout = QHBoxLayout(self.tab_calendar)
        self.calendar = QCalendarWidget(); self.calendar.setGridVisible(True); self.calendar.setFont(QFont("Segoe UI", 12))
        self.calendar.selectionChanged.connect(self.show_tasks_for_selected_date)
        self.day_tasks_list = QListWidget(); self.day_tasks_list.setFont(QFont("Segoe UI", 12)); self.day_tasks_list.setMinimumWidth(400)
        self.day_tasks_list.setWordWrap(True); self.day_tasks_list.itemClicked.connect(self.load_task_from_calendar)
        self.day_tasks_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.day_tasks_list.customContextMenuRequested.connect(self.show_calendar_dev_menu)
        cal_layout.addWidget(self.calendar, stretch=2); cal_layout.addWidget(self.day_tasks_list, stretch=1)
        self.tabs.addTab(self.tab_calendar, "Календарь")

    def setup_analytics_tab(self):
        self.tab_analytics = QWidget()
        analytics_layout = QVBoxLayout(self.tab_analytics)
        self.analytics_view = QTextBrowser()
        self.analytics_view.setFont(QFont("Segoe UI", 12))
        analytics_layout.addWidget(self.analytics_view)
        self.tabs.addTab(self.tab_analytics, "Аналитика")
        
    def setup_archive_tab(self):
        self.tab_archive = QWidget()
        archive_layout = QVBoxLayout(self.tab_archive)
        self.archive_manager = ArchiveTab() 
        archive_layout.addWidget(self.archive_manager)
        self.tabs.addTab(self.tab_archive, "Архив")

    def setup_settings_tab(self):
        self.tab_settings = QWidget()
        settings_layout = QVBoxLayout(self.tab_settings)
        settings_layout.setContentsMargins(15, 15, 15, 15)
        settings_layout.setSpacing(10)
        self.classic_settings_panel = SettingsPanelWidget(self.main_win, self.tab_settings)
        if hasattr(self.classic_settings_panel, 'load_settings'):
            self.classic_settings_panel.load_settings()
        settings_layout.addWidget(self.classic_settings_panel)
        self.tabs.addTab(self.tab_settings, "Настройки")

    def setup_dock(self):
        self.task_dock = QDockWidget("Список задач", self)
        self.task_dock.setObjectName("MainTaskDockWidget")
        self.task_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.task_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        
        task_container = QWidget(); task_layout = QVBoxLayout(task_container)
        
        self.clock_label = QLabel("00:00:00"); self.clock_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter); task_layout.addWidget(self.clock_label)
        
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Поиск...")
        self.search_input.textChanged.connect(self.refresh_task_list_ui)
        self.sort_combo = QComboBox(); self.sort_combo.addItems(["По дедлайну", "По алфавиту", "По статусу"])
        self.sort_combo.currentIndexChanged.connect(self.refresh_task_list_ui)
        filter_layout.addWidget(self.search_input); filter_layout.addWidget(self.sort_combo); task_layout.addLayout(filter_layout)
        
        self.task_list = QListWidget() 
        self.task_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.task_list.setFont(QFont("Segoe UI", 11)); self.task_list.setWordWrap(True)
        self.task_list.setStyleSheet("QListWidget::item { padding: 0px; margin: 0px; border: none; }")
        
        self.task_list.itemSelectionChanged.connect(self.on_task_selection_changed)
        self.task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self.show_context_menu)
        self.task_list.itemClicked.connect(self.load_task_to_center)
        task_layout.addWidget(self.task_list)
        
        self.add_btn = QPushButton("Добавить контракт (Ctrl+N)")
        self.add_btn.clicked.connect(lambda: getattr(self.main_win, 'add_task')())
        task_layout.addWidget(self.add_btn)
        
        bottom_layout = QHBoxLayout()
        self.version_label = QLabel(getattr(self.main_win, 'current_version', "v1.5"))
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(self.version_label)
        
        self.btn_update_indicator = QPushButton("🎁 Доступно обновление!")
        self.btn_update_indicator.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; padding: 2px;")
        self.btn_update_indicator.setVisible(False)
        self.btn_update_indicator.clicked.connect(lambda: getattr(self.main_win, 'trigger_pending_update')())
        bottom_layout.addWidget(self.btn_update_indicator)
        
        self.btn_mini_player = QPushButton("🗗")
        self.btn_mini_player.setFont(QFont("Segoe UI", 18)) # Делаем иконку крупной
        self.btn_mini_player.setToolTip("Плавающий таймер (Ctrl+M)")
        self.btn_mini_player.clicked.connect(lambda: getattr(self.main_win, 'toggle_mini_player')())
        bottom_layout.addWidget(self.btn_mini_player)
        
        self.btn_calc = QPushButton("🖩")
        self.btn_calc.setFont(QFont("Segoe UI", 18)) # Делаем иконку крупной
        self.btn_calc.setToolTip("Калькулятор (Ctrl+K)")
        self.btn_calc.clicked.connect(lambda: getattr(self.main_win, 'open_calculator')())
        bottom_layout.addWidget(self.btn_calc)
        
        task_layout.addLayout(bottom_layout)
        self.task_dock.setWidget(task_container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.task_dock)

    # --- 2. ЛОГИКА ОБНОВЛЕНИЯ И ОТОБРАЖЕНИЯ (Перенесено из TaskTimer.py) ---
    def on_tab_changed(self, index):
        if self.tabs.tabText(index) == "Архив":
            self.archive_manager.update_data(self.task_repo.get_all())
            
    def on_task_selection_changed(self):
        pass

    def get_current_task(self):
        if self.task_list.selectedItems():
            return self.task_list.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
        return None

    def refresh_all_views(self):
        self.refresh_task_list_ui()
        self.update_calendar_formats()
        self.show_tasks_for_selected_date()
        self.refresh_analytics()
        self.refresh_central_panel()

    def refresh_task_list_ui(self):
        self.task_list.setUpdatesEnabled(False) 
        scroll_pos = self.task_list.verticalScrollBar().value() 
        
        selected_ids = [item.data(Qt.ItemDataRole.UserRole).id for item in self.task_list.selectedItems()]
        self.task_list.clear()
        
        search_text = self.search_input.text().lower()
        sort_type = self.sort_combo.currentText()
        display_list = self.task_repo.get_all() 
        
        if sort_type == "По дедлайну": display_list.sort(key=lambda x: getattr(x, 'deadline', datetime.max))
        elif sort_type == "По алфавиту": display_list.sort(key=lambda x: x.client.lower())
        elif sort_type == "По статусу": display_list.sort(key=lambda x: x.status)

        for data in display_list:
            if data.status == "Завершено": continue
            if search_text and search_text not in data.client.lower() and search_text not in data.task.lower(): continue 
            
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, data)
            
            card_widget = TaskCardWidget(data, self.task_list)
            item.setSizeHint(QSize(self.task_list.viewport().width(), 70))
            
            self.task_list.addItem(item)
            self.task_list.setItemWidget(item, card_widget)
            item.setBackground(Qt.GlobalColor.transparent) 
            
            if data.id in selected_ids: 
                item.setSelected(True)
            
        self.task_list.verticalScrollBar().setValue(scroll_pos) 
        self.task_list.setUpdatesEnabled(True)

    def refresh_central_panel(self): 
        if self.task_list.selectedItems():
            self.load_task_to_center(self.task_list.selectedItems()[0])
        else:
            self.clear_central_panel()

    def clear_central_panel(self):
        self.lbl_client.setText("👤 Клиент: не выбран")
        self.lbl_task.setText("📌 Задача: ...")
        self.lbl_deadline.setText("⏳ Дедлайн: ...")
        self.lbl_spent.setText("⌛ Потрачено: 0 мин")
        self.task_details_widget.set_task(None)
        self.history_edit.clear()
        
        for btn in (self.btn_in_progress, self.btn_success, self.btn_reschedule, self.btn_screenshot, self.btn_complete): 
            btn.setEnabled(False)

    def load_task_to_center(self, item):
        task_obj = item.data(Qt.ItemDataRole.UserRole)
        time_spent = getattr(task_obj, 'time_spent', 0)
        spent_str = format_time_spent(time_spent)
        
        client = getattr(task_obj, 'client', '')
        task_name = getattr(task_obj, 'task', '')
        task_date = task_obj.deadline.strftime("%d.%m.%Y") if hasattr(task_obj, 'deadline') else ""
        task_time = task_obj.deadline.strftime("%H:%M") if hasattr(task_obj, 'deadline') else ""
        status = getattr(task_obj, 'status', '')
        
        self.lbl_client.setText(f"👤 Клиент: {client}")
        self.lbl_task.setText(f"📌 Задача: {task_name}")
        self.lbl_deadline.setText(f"⏳ Дедлайн: {task_date} в {task_time} [{status}]")
        self.lbl_spent.setText(f"⌛ Потрачено: {spent_str}")
        
        self.task_details_widget.set_task(task_obj)
        self.history_edit.setHtml(TaskService.generate_history_html(task_obj))
        
        self.btn_in_progress.setEnabled(status in ("Ожидание", "Время вышло"))
        self.btn_success.setEnabled(status == "В работе")
        self.btn_reschedule.setEnabled(status != "Завершено")
        self.btn_screenshot.setEnabled(status != "Завершено") 
        self.btn_complete.setEnabled(status != "Завершено") 

    def update_calendar_formats(self):
        for d in self.highlighted_dates: self.calendar.setDateTextFormat(d, QTextCharFormat())
        self.highlighted_dates.clear()
        pal = get_theme_palette(getattr(self.main_win, 'current_theme', 'dark_fantasy'))
        
        fmt_active = QTextCharFormat(); fmt_active.setBackground(QColor(pal["cal_active_bg"])); fmt_active.setForeground(QColor(pal["cal_active_fg"])); fmt_active.setFontWeight(QFont.Weight.Bold)
        fmt_completed = QTextCharFormat(); fmt_completed.setBackground(QColor(pal["cal_comp_bg"])); fmt_completed.setForeground(QColor(pal["cal_comp_fg"]))
        
        active_dates, completed_dates = set(), set()
        for data in self.task_repo.get_all():
            if hasattr(data, 'deadline'):
                d_str = data.deadline.strftime("%d.%m.%Y")
                if getattr(data, "status", "") in ("Завершено", "Успешно", "Выполнено"): completed_dates.add(d_str)
                else: active_dates.add(d_str)
            for hist_date in getattr(data, "completed_dates", []): completed_dates.add(hist_date)
            for h in getattr(data, "history", []):
                log_text = h.action if hasattr(h, 'action') else str(h)
                if "Затрачено:" in log_text or any(w in log_text.lower() for w in ["завершен", "успешн", "выполнен"]):
                    if hasattr(h, 'timestamp') and isinstance(h.timestamp, datetime):
                        completed_dates.add(h.timestamp.strftime("%d.%m.%Y"))
                    
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
        tasks_found, pal = False, get_theme_palette(getattr(self.main_win, 'current_theme', 'dark_fantasy'))
        
        for data in self.task_repo.get_all():
            task_date = data.deadline.strftime("%d.%m.%Y") if hasattr(data, 'deadline') else ""
            completed_dates = getattr(data, "completed_dates", [])
            is_current = (task_date == selected_date)
            is_history = (selected_date in completed_dates)
            
            history_logs = getattr(data, "history", [])
            spent_per_date = extract_spent_time_from_history(history_logs, task_date)
            history_time_str = spent_per_date.get(selected_date, "")
            
            has_activity_today = False
            for h in history_logs:
                log_text = h.action if hasattr(h, 'action') else str(h)
                ts_str = h.timestamp.strftime("%d.%m.%Y") if hasattr(h, 'timestamp') and isinstance(h.timestamp, datetime) else task_date
                if ts_str == selected_date and any(w in log_text.lower() for w in ["завершен", "успешн", "выполнен", "затрачено"]):
                    has_activity_today = True; break
            
            if is_current or is_history or has_activity_today:
                raw_status = getattr(data, "status", "Ожидание")
                if is_current and raw_status not in ("Успешно", "Завершено", "Выполнено"): status = raw_status
                else: status = f"Архив: {raw_status}" if raw_status in ("Успешно", "Завершено", "Выполнено") else "Архив: Выполнено"
                if is_current and raw_status in ("Успешно", "Завершено", "Выполнено"): status = raw_status
                
                if history_time_str: spent_str = f" | ⏱ {history_time_str}"
                else:
                    spent_seconds = getattr(data, 'time_spent', 0)
                    spent_str = f" | ⏱ {format_time_spent(spent_seconds)}" if spent_seconds > 0 else " | ⏱ 0м"
                
                task_time = data.deadline.strftime("%H:%M") if hasattr(data, 'deadline') else ""
                task_client = getattr(data, 'client', '')
                task_desc = getattr(data, 'task', '')
                task_id = getattr(data, 'id', None)
                
                day_item = QListWidgetItem(f"[{status}] {task_time} - {task_client}{spent_str}\nЗадача: {task_desc}")
                day_item.setData(Qt.ItemDataRole.UserRole, task_id) 
                
                if status in ("Завершено", "Успешно", "Выполнено") or "Архив" in status: day_item.setForeground(QColor(pal["completed"]))
                elif status == "В работе": day_item.setForeground(QColor(pal["in_progress"]))
                elif status == "Время вышло": day_item.setForeground(QColor(pal["expired"]))
                    
                self.day_tasks_list.addItem(day_item)
                tasks_found = True
                
        if not tasks_found: self.day_tasks_list.addItem("На этот день задач нет.")

    def load_task_from_calendar(self, day_item):
        target_id = day_item.data(Qt.ItemDataRole.UserRole)
        if not target_id: return
        task_obj = self.task_repo.get_by_id(target_id)
        if task_obj:
            for i in range(self.task_list.count()):
                item_obj = self.task_list.item(i).data(Qt.ItemDataRole.UserRole)
                if getattr(item_obj, "id", None) == target_id: 
                    self.task_list.item(i).setSelected(True)
                    break
            temp_item = QListWidgetItem()
            temp_item.setData(Qt.ItemDataRole.UserRole, task_obj)
            self.load_task_to_center(temp_item)
            self.tabs.setCurrentIndex(0)

    def refresh_analytics(self):
        all_tasks = self.task_repo.get_all()
        total_tasks = len(all_tasks)
        completed_tasks = sum(1 for t in all_tasks if getattr(t, "status", "") == "Завершено")
        curr_month = datetime.now().strftime(".%m.%Y")
        completed_this_month = sum(1 for t in all_tasks for d in getattr(t, "completed_dates", []) if curr_month in d)
        progress = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
        pal = get_theme_palette(getattr(self.main_win, 'current_theme', 'dark_fantasy'))
        
        html = f"""
        <div style="font-family: 'Segoe UI', sans-serif; color: {pal['menu_fg']}; padding: 20px;">
            <h2 style="color: {pal['in_progress']};">📊 Аналитика контрактов</h2>
            <hr style="border-top: 1px solid {pal['menu_sel']};">
            <table width="100%" cellpadding="10">
                <tr>
                    <td width="33%" style="background-color: {pal['menu_bg']}; border: 1px solid {pal['menu_sel']}; border-radius: 8px; text-align: center;">
                        <h1 style="margin: 0; color: {pal['clock']};">{total_tasks}</h1>
                        <p style="margin: 0; font-size: 14px;">Всего задач</p>
                    </td>
                    <td width="33%" style="background-color: {pal['menu_bg']}; border: 1px solid {pal['menu_sel']}; border-radius: 8px; text-align: center;">
                        <h1 style="margin: 0; color: {pal['completed']};">{completed_tasks}</h1>
                        <p style="margin: 0; font-size: 14px;">Завершено (Архив)</p>
                    </td>
                    <td width="33%" style="background-color: {pal['menu_bg']}; border: 1px solid {pal['menu_sel']}; border-radius: 8px; text-align: center;">
                        <h1 style="margin: 0; color: {pal['in_progress']};">{completed_this_month}</h1>
                        <p style="margin: 0; font-size: 14px;">Успешных этапов (Месяц)</p>
                    </td>
                </tr>
            </table>
            <br>
            <h3 style="color: {pal['menu_fg']};">Общий прогресс:</h3>
            <div style="background-color: {pal['menu_bg']}; border: 1px solid {pal['menu_sel']}; width: 100%; height: 30px;">
                <div style="background-color: {pal['in_progress']}; width: {progress}%; height: 100%;"></div>
            </div>
            <p style="text-align: right; margin-top: 5px; font-weight: bold;">{progress}%</p>
        </div>
        """
        self.analytics_view.setStyleSheet(f"background-color: {pal['history_bg']}; border: none;")
        self.analytics_view.setHtml(html)

    def show_context_menu(self, position):
        item = self.task_list.itemAt(position)
        if not item: return 
        item.setSelected(True); self.load_task_to_center(item) 
        current_data = item.data(Qt.ItemDataRole.UserRole)
        current_status = getattr(current_data, "status", "Ожидание")
        
        menu = QMenu(); pal = get_theme_palette(getattr(self.main_win, 'current_theme', 'dark_fantasy'))
        menu.setStyleSheet(f"QMenu {{ background-color: {pal['menu_bg']}; color: {pal['menu_fg']}; border: 1px solid {pal['menu_fg']}; font-size: 14px; }} QMenu::item {{ padding: 5px 20px; }} QMenu::item:selected {{ background-color: {pal['menu_sel']}; }}")
        
        start_action = success_action = reschedule_action = complete_action = screenshot_action = None
        if current_status in ("Ожидание", "Время вышло"): start_action = menu.addAction("Взять в работу"); complete_action = menu.addAction("Завершить (В историю)"); menu.addSeparator()
        elif current_status == "В работе": success_action = menu.addAction("Успешно (Перенос на месяц)"); reschedule_action = menu.addAction("Перенести вручную"); complete_action = menu.addAction("Завершить (В историю)"); menu.addSeparator()
            
        color_menu = menu.addMenu("🎨 Цвет тега")
        colors = get_tag_colors()
        for c_name, c_hex in colors.items():
            act = color_menu.addAction(c_name)
            act.triggered.connect(lambda checked, h=c_hex: events.action_change_color.emit(getattr(current_data, "id", None), h))
            
        menu.addSeparator()
        screenshot_action = menu.addAction("📸 Сделать скриншот (Ctrl+S)")
        open_folder_action = menu.addAction("📂 Открыть папку со скриншотами")
        if not getattr(self.main_win, 'screenshots_dir', None) or not os.path.exists(self.main_win.screenshots_dir): open_folder_action.setEnabled(False)
            
        open_screen_action = menu.addAction("🖼 Открыть последний скриншот")
        last_screenshot_path = None
        notes_value = getattr(current_data, "notes", "")
        if notes_value:
            matches = re.findall(r"\[Скриншот-отчет: (.+?)\]", notes_value)
            if matches: last_screenshot_path = matches[-1]
                
        if not last_screenshot_path or not os.path.exists(last_screenshot_path): open_screen_action.setEnabled(False)
            
        menu.addSeparator()
        edit_action = menu.addAction("Редактировать"); delete_action = menu.addAction("Удалить")
        
        action = menu.exec(self.task_list.mapToGlobal(position))
        
        if start_action and action == start_action: events.action_start_work.emit(current_data)
        elif success_action and action == success_action: events.action_mark_success.emit(current_data)
        elif reschedule_action and action == reschedule_action: events.action_reschedule_task.emit(current_data)
        elif complete_action and action == complete_action: events.action_complete_task.emit(current_data)
        elif screenshot_action and action == screenshot_action: events.action_screenshot.emit(current_data)
        elif action == open_folder_action: QDesktopServices.openUrl(QUrl.fromLocalFile(self.main_win.screenshots_dir))
        elif action == open_screen_action: QDesktopServices.openUrl(QUrl.fromLocalFile(last_screenshot_path))
        elif action == edit_action: events.action_edit_task.emit(current_data)
        elif action == delete_action: 
            from PyQt6.QtWidgets import QMessageBox
            if QMessageBox.question(self, 'Отмена', 'Точно удалить?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                events.action_delete_task.emit(current_data)

    def update_time_display(self):
        if not self.task_list.selectedItems(): return
        task_obj = self.task_list.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
        if getattr(task_obj, "status", "") == "В работе":
            tz_off = getattr(self.main_win, 'tz_offset', 3)
            _, spent_str = calculate_dynamic_time(task_obj, tz_off)
            self.lbl_spent.setText(f"⌛ Потрачено: {spent_str}")

    def update_timers_and_clock(self):
        """Обновляет визуальные часы и таймеры в карточках боковой панели"""
        tz_off = getattr(self.main_win, 'tz_offset', 3)
        current_tz = timezone(timedelta(hours=tz_off))
        current_time = datetime.now(current_tz)
        
        if hasattr(self, 'clock_label'):
            self.clock_label.setText(current_time.strftime("%H:%M:%S"))
        self.update_time_display()
            
        if hasattr(self, 'task_list'):
            self.task_list.setUpdatesEnabled(False)
            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)
                card_widget = self.task_list.itemWidget(item)
                
                if not card_widget or getattr(data, "status", "") == "Завершено": 
                    continue
                    
                if getattr(data, "status", "") == "Ожидание" and hasattr(data, "deadline"):
                    try:
                        task_dt = data.deadline.replace(tzinfo=current_tz)
                        if current_time < task_dt:
                            countdown_str = calculate_countdown_status(task_dt, current_time)
                            card_widget.update_countdown(countdown_str)
                    except ValueError: pass
                else: card_widget.update_countdown("")
            self.task_list.setUpdatesEnabled(True)
    
    # === СТАНДАРТИЗИРОВАННЫЕ МЕТОДЫ ИНТЕРФЕЙСА (SOLID) ===
    def get_settings_panel(self):
        return getattr(self, 'classic_settings_panel', None)

    def update_settings_ui(self, data):
        panel = self.get_settings_panel()
        if panel and hasattr(panel, 'load_from_data'):
            panel.load_from_data(data)

    def apply_theme(self, palette):
        if hasattr(self, 'archive_manager'):
            self.archive_manager.apply_theme(palette)
        self.update_calendar_formats()
        self.refresh_analytics()
    
    def get_layout_state(self):
        """Возвращает размеры панелей и сплиттеров для сохранения (Стандарт SOLID)"""
        from PyQt6.QtCore import QByteArray
        state = {
            # Сохраняем ширину и позицию док-панели (Список задач)
            "dock_state": self.saveState().toBase64().data().decode('utf-8')
        }
        # Сохраняем пропорции центрального разделителя (между задачей и историей)
        if hasattr(self, 'splitter'):
            state["splitter_state"] = self.splitter.saveState().toBase64().data().decode('utf-8')
        return state

    def restore_layout_state(self, state_dict):
        """Восстанавливает размеры панелей и сплиттеров (Стандарт SOLID)"""
        from PyQt6.QtCore import QByteArray
        if not state_dict: return
        
        if state_dict.get("dock_state"):
            self.restoreState(QByteArray.fromBase64(state_dict["dock_state"].encode('utf-8')))
            
        if state_dict.get("splitter_state") and hasattr(self, 'splitter'):
            self.splitter.restoreState(QByteArray.fromBase64(state_dict["splitter_state"].encode('utf-8')))
            
    
    def show_calendar_dev_menu(self, pos):
        if getattr(self.main_win, 'dev_mode', False):
            from tabs.dev_tools import show_dev_context_menu
            show_dev_context_menu(self.day_tasks_list, pos, self.task_repo)
            
# --- ДОБАВИТЬ СЮДА, В САМЫЙ НИЗ, БЕЗ ОТСТУПОВ ---
from tabs.events import register_workspace
register_workspace("Классический вид", ClassicWorkspace)