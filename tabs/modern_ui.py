from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, 
                             QScrollArea, QStackedWidget, QTextEdit,
                             QListWidget, QListWidgetItem, QTextBrowser, QLineEdit, QMenu, QGridLayout, QComboBox, QCalendarWidget)
from PyQt6.QtGui import QFont, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from datetime import datetime, timezone, timedelta
from tabs.services import TaskService
from tabs.notes import NotesManager
from tabs.settings import SettingsPanelWidget
from tabs.themes import get_theme_palette
from tabs.utils import calculate_dynamic_time, calculate_countdown_status, extract_spent_time_from_history, format_time_spent
from tabs.widgets import TaskDetailsWidget
from tabs.archive import ArchiveTab
from tabs.events import events
from tabs.calendar import ModernCalendarWidget
from tabs.base_workspace import WorkspaceContract
from tabs.dialogs import ModernTaskDialog

class TaskCard(QFrame):
    clicked = pyqtSignal(object, object)
    
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setFixedHeight(80)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.set_selected(False)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        client_name = getattr(task, 'client', 'Без клиента')
        task_desc = getattr(task, 'task', 'Без описания')
        task_status = getattr(task, 'status', 'Ожидание')
        deadline_obj = getattr(task, 'deadline', None)
        deadline_str = deadline_obj.strftime("%d.%m.%Y %H:%M") if deadline_obj else ""

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.client_lbl = QLabel(str(client_name), self)
        self.client_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        
        self.desc_lbl = QLabel(str(task_desc), self)
        self.desc_lbl.setFont(QFont("Segoe UI", 11))
        
        text_layout.addWidget(self.client_lbl)
        text_layout.addWidget(self.desc_lbl)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.status_lbl = QLabel(str(task_status), self)
        self.status_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        
        self.deadline_lbl = QLabel(f"⏳ {deadline_str}", self)
        self.deadline_lbl.setFont(QFont("Segoe UI", 10))
        
        self.countdown_lbl = QLabel("", self)
        self.countdown_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.countdown_lbl.setVisible(False) 
        
        info_layout.addWidget(self.status_lbl)
        info_layout.addWidget(self.deadline_lbl)
        info_layout.addWidget(self.countdown_lbl)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addLayout(info_layout)
        
        self.btn_action = QPushButton("▶", self)
        self.btn_action.setFixedSize(40, 40)
        self.btn_action.setFont(QFont("Segoe UI", 12))
        
        if task_status == "В работе":
            self.btn_action.setText("✅")

        layout.addWidget(self.btn_action)
        
        # ВАЖНО: Применяем стили в самом конце, когда все виджеты (labels, buttons) уже созданы!
        self.apply_theme_styles()

    def apply_theme_styles(self):
        """Строгое применение палитры темы для карточки задачи"""
        main_window = self.window()
        theme_name = getattr(main_window, 'current_theme', 'dark_fantasy') if main_window else 'dark_fantasy'
        pal = get_theme_palette(theme_name)

        card_bg = pal['cal_comp_bg']
        border_color = pal['version']
        accent_color = pal['in_progress']
        text_color = pal['menu_fg']
        desc_color = pal['history_fg']
        hover_bg = pal['menu_sel']

        # 1. Сама карточка
        self.setStyleSheet(f"""
            TaskCard {{ background-color: {card_bg}; border-radius: 8px; border: 1px solid {border_color}; border-left: 6px solid {accent_color}; }}
            TaskCard[selected="true"] {{ background-color: {hover_bg}; border: 1px solid {accent_color}; border-left: 6px solid {accent_color}; }}
            TaskCard:hover {{ background-color: {hover_bg}; border: 1px solid {accent_color}; border-left: 6px solid {accent_color}; }}
        """)

        # 2. Текстовые метки
        self.client_lbl.setStyleSheet(f"color: {text_color}; border: none; background: transparent;")
        self.desc_lbl.setStyleSheet(f"color: {desc_color}; border: none; background: transparent;")
        self.deadline_lbl.setStyleSheet(f"color: {desc_color}; border: none; background: transparent;")
        
        # 3. Статусы и кнопки
        task_status = getattr(self.task, 'status', 'Ожидание')
        if task_status == "В работе":
            self.status_lbl.setStyleSheet(f"color: {pal['clock']}; border: none; background: transparent;")
            self.btn_action.setStyleSheet(f"""
                QPushButton {{ background-color: rgba(46, 204, 113, 0.15); color: {pal['clock']}; border-radius: 20px; border: none; }}
                QPushButton:hover {{ background-color: {pal['clock']}; color: {card_bg}; }}
            """)
        else:
            self.status_lbl.setStyleSheet(f"color: {accent_color}; border: none; background: transparent;")
            self.btn_action.setStyleSheet(f"""
                QPushButton {{ background-color: rgba(128, 128, 128, 0.2); color: {accent_color}; border-radius: 20px; border: none; }}
                QPushButton:hover {{ background-color: {accent_color}; color: {card_bg}; }}
            """)
            
        self.countdown_lbl.setStyleSheet(f"color: {pal['clock']}; background: rgba(77, 182, 172, 0.1); padding: 4px; border-radius: 4px;")

    def set_selected(self, selected):
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.task, event.modifiers())
        super().mousePressEvent(event)

    def update_countdown(self, text):
        if text:
            self.countdown_lbl.setText(text)
            self.countdown_lbl.setVisible(True)
        else:
            self.countdown_lbl.setVisible(False)


class ModernWorkspace(QWidget, WorkspaceContract):
    dialog_class = ModernTaskDialog
    is_modern_style = True

    def __init__(self, task_repo, controller, parent=None):
        super().__init__(parent)
        # Удалите отсюда строки self.dialog_class = ... и self.is_modern_style = ...
        self.task_repo = task_repo
        self.controller = controller
        self.current_task = None  # Запоминаем открытую задачу
        
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(20)
        
        self.setup_ui()
        self.refresh_data()
        
        events.timer_tick.connect(self.update_timers)
        
        # --- Массивы для мульти-выделения (Shift/Ctrl) ---
        self.selected_tasks = []
        self.last_clicked_task = None
        # Подписываемся на глобальное событие изменения данных
        events.data_changed.connect(self.refresh_data)
        

    def setup_ui(self):
        # 1. Левая панель (Навигация / Меню)
        self.sidebar_layout = QVBoxLayout()
        self.sidebar_layout.setSpacing(10)
        
        self.clock_lbl = QLabel("00:00:00")
        self.clock_lbl.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.clock_lbl.setStyleSheet("color: #4DB6AC; padding-bottom: 10px;")
        self.clock_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(self.clock_lbl)
                
        self.sidebar_layout.addSpacing(20)
        
        self.btn_add_task = QPushButton("➕ Новый контракт")
        self.btn_add_task.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        # Стилизация кнопки добавления задачи задается в apply_workspace_theme
        self.btn_add_task.clicked.connect(self.trigger_add_task)
        self.sidebar_layout.addWidget(self.btn_add_task)
        
        self.sidebar_layout.addSpacing(10)
        
        self.btn_tasks = QPushButton("📌 Задачи")
        self.btn_calendar = QPushButton("📅 Календарь")
        self.btn_notes = QPushButton("📝 Заметки")
        self.btn_menu_archive = QPushButton("📦 Архив")
        self.btn_settings = QPushButton("⚙ Настройки")
        
        # 1. Добавляем ОСНОВНЫЕ кнопки навигации (БЕЗ калькулятора)
        for btn in (self.btn_tasks, self.btn_calendar, self.btn_notes, self.btn_menu_archive, self.btn_settings):
            btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            btn.setMinimumHeight(45)
            btn.setProperty("modernMenuBtn", "true")
            self.sidebar_layout.addWidget(btn)
            
        # Пружина, которая выталкивает основные вкладки вверх, а утилиты — в самый низ
        self.sidebar_layout.addStretch()
        
        # 2. МИНИМАЛИСТИЧНЫЕ УТИЛИТЫ (Всплывающие окна внизу)
        self.btn_calculator = QPushButton("🖩 Калькулятор")
        self.btn_calculator.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.btn_calculator.setMinimumHeight(45)
        self.btn_calculator.clicked.connect(lambda: self.window().open_calculator()) # <-- Возвращаем функционал
        self.sidebar_layout.addWidget(self.btn_calculator)
        
        self.btn_mini_player = QPushButton("🗗 Плавающий таймер")
        self.btn_mini_player.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.btn_mini_player.setMinimumHeight(45)
        self.btn_mini_player.clicked.connect(lambda: self.window().toggle_mini_player()) # <-- Возвращаем функционал
        self.sidebar_layout.addWidget(self.btn_mini_player)

        # 2. Центральная панель
        self.content_stack = QStackedWidget()
        # ... дальше идет ваш код (self.page_tasks = QWidget() и т.д.) ...
        
        self.page_tasks = QWidget()
        page_tasks_layout = QVBoxLayout(self.page_tasks)
        page_tasks_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tasks_scroll = QScrollArea()
        self.tasks_scroll.setWidgetResizable(True)
        # ВЫЧИСТИЛИ ЖЕСТКИЙ ЦВЕТ ОТСЮДА:
        self.tasks_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 10px; background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.3); }
        """)
        
        self.tasks_container = QWidget()
        # И ВЫЧИСТИЛИ ОТСЮДА:
        self.tasks_container.setStyleSheet("background: transparent;")
        
        self.tasks_list_layout = QVBoxLayout(self.tasks_container)
        self.tasks_list_layout.setSpacing(10)  # Отступ между карточками
        self.tasks_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tasks_list_layout.setContentsMargins(15, 15, 15, 15)
        
        self.tasks_scroll.setWidget(self.tasks_container)
        page_tasks_layout.addWidget(self.tasks_scroll)
        self.content_stack.addWidget(self.page_tasks)
        
        # --- СТРАНИЦА: КАЛЕНДАРЬ (индекс 1) ---
        self.page_calendar = QWidget()
        page_calendar_layout = QHBoxLayout(self.page_calendar)
        page_calendar_layout.setContentsMargins(0, 10, 15, 10)
        
        self.modern_calendar = ModernCalendarWidget( parent=self, get_theme_cb=lambda: getattr(self.window(), 'current_theme', 'dark_fantasy'))
        self.modern_calendar.selectionChanged.connect(self.update_modern_calendar_tasks)
        
        self.modern_day_tasks = QListWidget()
        self.modern_day_tasks.setFont(QFont("Segoe UI", 11))
        self.modern_day_tasks.setWordWrap(True)
        self.modern_day_tasks.itemClicked.connect(self.load_task_from_modern_calendar)
        
        self.modern_day_tasks.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.modern_day_tasks.customContextMenuRequested.connect(self.show_calendar_dev_menu)
        
        page_calendar_layout.addWidget(self.modern_calendar, stretch=2)
        page_calendar_layout.addWidget(self.modern_day_tasks, stretch=1)
        self.content_stack.addWidget(self.page_calendar)
        
        # --- СТРАНИЦА: ОБЩИЕ ЗАМЕТКИ (индекс 2) ---
        self.page_notes = QWidget(self.content_stack)
        page_notes_layout = QVBoxLayout(self.page_notes)
        page_notes_layout.setContentsMargins(0, 10, 15, 10)
        
        notes_header = QLabel("Общие заметки", self.page_notes)
        notes_header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        notes_header.setStyleSheet("color: #ffffff;")
        
        # ВАЖНО: Добавили жесткую привязку, как в классическом интерфейсе!
        self.modern_notes_manager = NotesManager(self.controller.get_notes)
        self.modern_notes_manager.setParent(self.page_notes)
        
        # Идеально выверенный современный стиль для заметок
        self.modern_notes_manager.setStyleSheet("""
            QTabWidget::pane { 
                border: none; 
                background: transparent; 
            }
            QTabWidget::tab-bar { 
                alignment: left; 
            }
            
            /* Основной стиль вкладок */
            QTabBar::tab { 
                background: rgba(255, 255, 255, 0.05); 
                color: #8b949e; 
                padding: 8px 16px; /* Равномерные отступы, Qt сам добавит место под крестик */
                border-radius: 6px; 
                margin-right: 6px; 
                margin-bottom: 15px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                font-size: 13px;
                font-family: "Segoe UI";
            }
            QTabBar::tab:selected { 
                background: rgba(46, 204, 113, 0.15); 
                color: #2ecc71; 
                border: 1px solid rgba(46, 204, 113, 0.3);
            }
            QTabBar::tab:hover:!selected { 
                background: rgba(255, 255, 255, 0.1); 
                color: #ffffff; 
            }
            
            /* ---- ИДЕАЛЬНАЯ КНОПКА ЗАКРЫТИЯ (ВЕКТОР) ---- */
            QTabBar::close-button {
                subcontrol-position: right center; /* Жестко по центру справа */
                margin-right: 4px; /* Легкий отступ от края */
                width: 14px;
                height: 14px;
                /* Отрисовываем серый крестик через встроенный SVG */
                image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%238b949e' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><line x1='18' y1='6' x2='6' y2='18'></line><line x1='6' y1='6' x2='18' y2='18'></line></svg>");
            }
            
            /* Цветной крестик для активной вкладки */
            QTabBar::tab:selected QTabBar::close-button {
                image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ecc71' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><line x1='18' y1='6' x2='6' y2='18'></line><line x1='6' y1='6' x2='18' y2='18'></line></svg>");
            }
            
            /* Красный фон и белый крестик при наведении */
            QTabBar::close-button:hover {
                image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ffffff' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><line x1='18' y1='6' x2='6' y2='18'></line><line x1='6' y1='6' x2='18' y2='18'></line></svg>");
                background: #e74c3c;
                border-radius: 4px;
            }

            /* ПОЛЕ ВВОДА ТЕКСТА */
            QTextEdit { 
                background-color: rgba(0, 0, 0, 0.2); 
                color: #e0e0e0; 
                border-radius: 12px; 
                padding: 15px;
                border: 1px solid rgba(255, 255, 255, 0.05); 
                font-size: 14px;
            }
            
            /* НЕВИДИМЫЕ СКРОЛЛБАРЫ */
            QScrollBar:vertical { 
                width: 8px; 
                background: transparent; 
                margin: 0px;
            }
            QScrollBar::handle:vertical { 
                background: rgba(255, 255, 255, 0.15); 
                border-radius: 4px; 
            }
            QScrollBar::handle:vertical:hover { 
                background: rgba(255, 255, 255, 0.3); 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        page_notes_layout.addWidget(notes_header)
        page_notes_layout.addWidget(self.modern_notes_manager)
        self.content_stack.addWidget(self.page_notes)
        
        # --- СТРАНИЦА: АРХИВ (индекс 3) ---
        self.page_archive = QWidget()
        page_archive_layout = QVBoxLayout(self.page_archive)
        page_archive_layout.setContentsMargins(0, 10, 15, 10)
        
        archive_header = QLabel("Архив выполненных задач", self.page_archive)
        archive_header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        archive_header.setStyleSheet("color: #ffffff;")
        
        self.modern_archive_tab = ArchiveTab(self.page_archive)
        
        page_archive_layout.addWidget(archive_header)
        page_archive_layout.addWidget(self.modern_archive_tab)
        self.content_stack.addWidget(self.page_archive)
        
       # --- СТРАНИЦА: НАСТРОЙКИ (индекс 4) ---
        self.page_settings = QWidget()
        page_layout = QVBoxLayout(self.page_settings)
        page_layout.setContentsMargins(0, 10, 15, 10)
        page_layout.setSpacing(15)
        
        settings_header = QLabel("Настройки приложения")
        settings_header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        settings_header.setStyleSheet("color: #ffffff;")
        
        self.settings_panel = SettingsPanelWidget(self.window(), self)
        page_layout.addWidget(settings_header)
        page_layout.addWidget(self.settings_panel)
        self.content_stack.addWidget(self.page_settings)

        # =========================================================================
        # 3. ПРАВАЯ ПАНЕЛЬ (Детали выбранной задачи) — создаем ЕЕ СРАЗУ ЗДЕСЬ
        # =========================================================================
        self.details_panel = QFrame()
        self.details_panel.setFixedWidth(420)
        self.details_panel.setObjectName("modernDetailsPanel")
        
        panel_layout = QVBoxLayout(self.details_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        self.det_scroll = QScrollArea()
        self.det_scroll.setWidgetResizable(True)
        self.det_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 8px; background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.2); border-radius: 4px; }
        """)
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.details_layout = QVBoxLayout(scroll_content)
        self.details_layout.setContentsMargins(20, 25, 20, 20)
        self.details_layout.setSpacing(15)
        
        self.det_client_lbl = QLabel("Выберите задачу")
        self.det_client_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.det_client_lbl.setStyleSheet("border: none; background: transparent;")
        self.det_client_lbl.setWordWrap(True)
        
        self.det_status_lbl = QLabel("")
        self.det_status_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.det_status_lbl.setStyleSheet("color: #e67e22; border: none;")
        
        self.det_desc_lbl = QLabel("Здесь будет отображаться описание...")
        self.det_desc_lbl.setFont(QFont("Segoe UI", 12))
        self.det_desc_lbl.setStyleSheet("color: #b0b0b0; border: none;")
        self.det_desc_lbl.setWordWrap(True)
        
        self.det_info_lbl = QLabel("")
        self.det_info_lbl.setFont(QFont("Segoe UI", 11))
        self.det_info_lbl.setStyleSheet("color: #8b949e; border: none;")
        
        self.task_details_widget = TaskDetailsWidget(scroll_content)
        
        history_label = QLabel("История изменений:")
        history_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        history_label.setStyleSheet("border: none; padding-top: 10px; background: transparent;")
        
        self.det_history = QTextBrowser()
        self.det_history.setFont(QFont("Segoe UI", 11))
        self.det_history.setStyleSheet("""
            QTextBrowser {
                background: rgba(0, 0, 0, 0.2); 
                color: #cccccc; 
                border-radius: 8px; 
                padding: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        self.det_history.setMinimumHeight(150)

        self.details_layout.addWidget(self.det_client_lbl)
        self.details_layout.addWidget(self.det_status_lbl)
        self.details_layout.addWidget(self.det_desc_lbl)
        self.details_layout.addWidget(self.det_info_lbl)
        self.details_layout.addWidget(self.task_details_widget)
        self.details_layout.addWidget(history_label)
        self.details_layout.addWidget(self.det_history)
        self.details_layout.addStretch()
        
        self.det_scroll.setWidget(scroll_content)
        panel_layout.addWidget(self.det_scroll)
        
        actions_layout = QGridLayout()
        actions_layout.setContentsMargins(15, 0, 15, 15)
        actions_layout.setSpacing(10)
        
        self.btn_play = QPushButton("▶ В работу")
        self.btn_success = QPushButton("✅ Успешно")
        self.btn_archive = QPushButton("🏁 В архив")
        self.btn_reschedule = QPushButton("📅 Перенести")
        self.btn_screenshot = QPushButton("📸 Скриншот")
        
        for btn in (self.btn_play, self.btn_success, self.btn_reschedule, self.btn_screenshot, self.btn_archive):
            btn.setMinimumHeight(42)
            btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            btn.setStyleSheet("""
                QPushButton { 
                    background-color: rgba(255, 255, 255, 0.08); 
                    color: #ffffff; 
                    border-radius: 6px; 
                }
                QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }
                QPushButton:disabled { background-color: rgba(0, 0, 0, 0.2); color: #666666; }
            """)
            btn.setEnabled(False)
            
        actions_layout.addWidget(self.btn_play, 0, 0)
        actions_layout.addWidget(self.btn_success, 0, 1)
        actions_layout.addWidget(self.btn_archive, 0, 2)
        actions_layout.addWidget(self.btn_reschedule, 1, 0, 1, 1)
        actions_layout.addWidget(self.btn_screenshot, 1, 1, 1, 2)
        
        panel_layout.addLayout(actions_layout)

        # Сборка общего главного макета
        self.main_layout.addLayout(self.sidebar_layout, stretch=1)
        self.main_layout.addWidget(self.content_stack, stretch=4)
        self.main_layout.addWidget(self.details_panel, stretch=2)
        
        self.details_panel.setVisible(False)  # Изначально скрыта

        # =========================================================================
        # 4. ПОДКЛЮЧАЕМ ВСЕ СИГНАЛЫ КНОПОК (когда всё уже создано)
        # =========================================================================
        self.btn_tasks.clicked.connect(lambda: (
            self.content_stack.setCurrentIndex(0), 
            self.details_panel.setVisible(self.current_task is not None)
        ))
        self.btn_calendar.clicked.connect(lambda: (
            self.update_modern_calendar_tasks(), 
            self.content_stack.setCurrentIndex(1), 
            self.details_panel.setVisible(False)
        ))
        self.btn_notes.clicked.connect(lambda: (
            self.content_stack.setCurrentIndex(2), 
            self.details_panel.setVisible(False)
        ))
        self.btn_menu_archive.clicked.connect(lambda: (
            self.modern_archive_tab.update_data(self.task_repo.get_all()), 
            self.content_stack.setCurrentIndex(3), 
            self.details_panel.setVisible(False)
        ))
        self.btn_settings.clicked.connect(lambda: (
            self.content_stack.setCurrentIndex(4), 
            self.details_panel.setVisible(False)
        ))

        # --- СВЯЗЬ КНОПОК УПРАВЛЕНИЯ ЗАДАЧЕЙ ЧЕРЕЗ ШИНУ СОБЫТИЙ ---
        self.btn_play.clicked.connect(lambda: events.action_start_work.emit(self.current_task))
        self.btn_success.clicked.connect(lambda: events.action_mark_success.emit(self.current_task))
        self.btn_archive.clicked.connect(lambda: events.action_complete_task.emit(self.current_task))
        self.btn_reschedule.clicked.connect(lambda: events.action_reschedule_task.emit(self.current_task))
        self.btn_screenshot.clicked.connect(lambda: events.action_screenshot.emit(self.current_task))
        self.btn_calculator.clicked.connect(lambda: self.window().open_calculator())
    
    # === СТАНДАРТИЗИРОВАННЫЕ МЕТОДЫ ИНТЕРФЕЙСА (SOLID) ===
    def get_current_task(self):
        return getattr(self, 'current_task', None)

    def get_settings_panel(self):
        return getattr(self, 'settings_panel', None)

    def update_settings_ui(self, data):
        panel = self.get_settings_panel()
        if panel and hasattr(panel, 'load_from_data'):
            panel.load_from_data(data)

    def apply_theme(self, palette):
        """Метод принимает палитру напрямую от менеджера экранов"""
        # Сначала сохраняем палитру для использования при перерисовке данных
        self._current_palette = palette

        bg_main = palette['menu_bg']
        bg_comp = palette['cal_comp_bg']
        accent = palette['in_progress']
        fg_text = palette['menu_fg']
        border_col = palette['version']
        sel_col = palette['menu_sel']
        clock_col = palette['clock']
        history_fg = palette['history_fg']
        history_bg = palette['history_bg']
        completed = palette['completed']
        expired = palette['expired']
        
        if hasattr(self, 'modern_archive_tab') and self.modern_archive_tab:
            self.modern_archive_tab.apply_theme(palette)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"ModernWorkspace {{ background-color: {bg_main}; }}")
        
        self.page_tasks.setStyleSheet(f"background-color: {bg_main};")
        self.tasks_container.setStyleSheet(f"background-color: {bg_main};")
        
        self.tasks_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background-color: {bg_main}; }}
            QScrollBar:vertical {{ width: 10px; background: {bg_main}; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: {border_col}; border-radius: 5px; }}
            QScrollBar::handle:vertical:hover {{ background: {accent}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; background: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)
        
        if self.tasks_scroll.viewport():
            self.tasks_scroll.viewport().setStyleSheet(f"background-color: {bg_main};")

        if hasattr(self, 'clock_lbl'):
            self.clock_lbl.setStyleSheet(f"color: {clock_col}; padding-bottom: 10px;")
        
        self.btn_add_task.setStyleSheet(f"""
            QPushButton {{ background-color: {accent}; color: {bg_main}; border-radius: 8px; padding: 12px; text-align: left; padding-left: 15px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {sel_col}; color: {accent}; border: 1px solid {accent}; }}
        """)

        for btn in (self.btn_tasks, self.btn_calendar, self.btn_notes, self.btn_menu_archive, self.btn_settings):
            btn.setStyleSheet(f"""
                QPushButton {{ text-align: left; padding: 10px 15px; border: 1px solid {border_col}; border-radius: 8px; background: transparent; color: {fg_text}; }}
                QPushButton:hover {{ background-color: {sel_col}; color: {accent}; border: 1px solid {accent}; }}
                QPushButton:pressed {{ background-color: rgba(0, 0, 0, 0.2); }}
            """)

        self.details_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.details_panel.setStyleSheet(f"#modernDetailsPanel {{ background-color: {bg_main}; }}")
        
        self.det_status_lbl.setStyleSheet(f"color: {accent}; border: none; background: transparent;")
        self.det_desc_lbl.setStyleSheet(f"color: {history_fg}; border: none; background: transparent;")
        self.det_info_lbl.setStyleSheet(f"color: {border_col}; border: none; background: transparent;")
        self.det_client_lbl.setStyleSheet(f"color: {fg_text}; border: none; background: transparent;")
        
        input_style = f"background: {bg_comp}; color: {fg_text}; border-radius: 8px; padding: 10px; border: 1px solid {border_col};"
        self.det_history.setStyleSheet(f"QTextBrowser {{ {input_style} }}")

        for btn in (self.btn_play, self.btn_success, self.btn_reschedule, self.btn_screenshot, self.btn_archive):
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {bg_comp}; color: {fg_text}; border-radius: 6px; border: 1px solid {border_col}; }}
                QPushButton:hover {{ background-color: {sel_col}; border: 1px solid {accent}; }}
                QPushButton:disabled {{ background-color: {bg_main}; color: {border_col}; border: none; }}
            """)

        if hasattr(self, 'modern_calendar') and hasattr(self, 'modern_day_tasks'):
            self.modern_calendar.setStyleSheet(f"""
                QCalendarWidget QWidget {{ background-color: {bg_comp}; color: {fg_text}; }}
                QCalendarWidget QToolButton {{ background-color: {bg_main}; color: {fg_text}; border: 1px solid {border_col}; border-radius: 8px; margin: 4px; padding: 6px 14px; font-weight: bold; }}
                QCalendarWidget QToolButton:hover {{ background-color: {sel_col}; border: 1px solid {accent}; color: {accent}; }}
                QCalendarWidget QMenu {{ background-color: {bg_comp}; color: {fg_text}; border: 1px solid {border_col}; }}
                QCalendarWidget QTableView {{ background-color: {bg_comp}; selection-background-color: transparent; border: 1px solid {border_col}; border-radius: 12px; outline: none; }}
                QCalendarWidget QHeaderView::section {{ background-color: {bg_main}; color: {history_fg}; padding: 6px; border: none; font-weight: bold; }}
            """)

            self.modern_day_tasks.setStyleSheet(f"""
                QListWidget {{ background-color: {bg_comp}; color: {fg_text}; border: 1px solid {border_col}; border-radius: 8px; padding: 8px; }}
                QListWidget::item {{ background-color: {bg_main}; color: {fg_text}; padding: 10px; border-radius: 6px; margin-bottom: 6px; border: 1px solid {border_col}; }}
                QListWidget::item:hover {{ background-color: {sel_col}; border: 1px solid {accent}; }}
                QListWidget::item:selected {{ background-color: {sel_col}; border: 1px solid {accent}; color: {accent}; }}
            """)

        if hasattr(self, 'settings_panel'):
            self.settings_panel.setStyleSheet(f"""
                QWidget {{ background-color: transparent; color: {fg_text}; }}
                QLabel {{ font-size: 13px; font-weight: bold; border: none; }}
                QLabel#sub_label {{ color: {border_col}; font-size: 12px; font-weight: normal; }}
                QComboBox, QLineEdit {{ background-color: {bg_comp}; color: {fg_text}; border-radius: 8px; padding: 8px 12px; border: 1px solid {border_col}; }}
                QComboBox:hover, QLineEdit:hover, QComboBox:focus, QLineEdit:focus {{ border: 1px solid {accent}; }}
                QComboBox::drop-down {{ width: 30px; border: none; }}
                QComboBox QAbstractItemView {{ background-color: {bg_comp}; color: {fg_text}; selection-background-color: {sel_col}; selection-color: {accent}; border: 1px solid {border_col}; border-radius: 6px; outline: none; }}
                QPushButton {{ background-color: {bg_comp}; color: {fg_text}; border: 1px solid {border_col}; border-radius: 8px; padding: 8px 12px; font-weight: bold; }}
                QPushButton:hover {{ background-color: {sel_col}; border: 1px solid {accent}; color: {accent}; }}
                QPushButton#primary_btn {{ border-color: {accent}; color: {accent}; background: rgba(52,152,219,0.05); }}
                QPushButton#primary_btn:hover {{ background: {sel_col}; }}
                QPushButton#success_btn {{ border-color: {completed}; color: {completed}; background: rgba(46,204,113,0.05); }}
                QPushButton#success_btn:hover {{ background: {sel_col}; border-color: {accent}; color: {accent}; }}
                QPushButton#danger_btn {{ border-color: {expired}; color: {expired}; background: rgba(231,76,60,0.05); }}
                QPushButton#danger_btn:hover {{ background: {sel_col}; border-color: {accent}; color: {accent}; }}
                QCheckBox {{ font-size: 13px; font-weight: normal; }}
                QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {border_col}; background-color: {bg_comp}; }}
                QCheckBox::indicator:checked {{ background-color: {accent}; border: 1px solid {accent}; }}
                QSlider::groove:horizontal {{ height: 6px; background: {border_col}; border-radius: 3px; }}
                QSlider::handle:horizontal {{ background: {accent}; width: 16px; margin: -5px 0; border-radius: 8px; }}
                QFrame[frameShape="4"] {{ background-color: {border_col}; max-height: 1px; border: none; }}
            """)
            
        utility_style = f"""
            QPushButton {{ text-align: left; padding-left: 15px; border: none; border-radius: 8px; color: {clock_col}; background-color: {bg_comp}; }}
            QPushButton:hover {{ background-color: {sel_col}; color: {accent}; }}
        """
        self.btn_mini_player.setStyleSheet(utility_style)
        if hasattr(self, 'btn_calculator'):
            self.btn_calculator.setStyleSheet(utility_style)

        # === ОБНОВЛЯЕМ ЦВЕТА УЖЕ СОЗДАННЫХ КАРТОЧЕК ===
        for i in range(self.tasks_list_layout.count()):
            item = self.tasks_list_layout.itemAt(i)
            if item and item.widget():
                card_widget = item.widget()
                # Проверяем, что это именно карточка задачи, а не пустой лейбл
                if hasattr(card_widget, 'apply_theme_styles'):
                    card_widget.apply_theme_styles()
        
    def trigger_add_task(self):
        """Вызывает оригинальное окно создания задачи и обновляет интерфейс"""
        main_window = self.window()
        if hasattr(main_window, 'add_task'):
            # Явно указываем, что хотим открыть современное окно
            main_window.add_task(is_modern=True)  
            self.refresh_data()

    def update_timers(self):
        """Ежесекундно пересчитывает время для карточек и обновляет главные часы"""
        main_window = self.window()
        if not hasattr(main_window, 'tz_offset'): 
            return
            
        tz = timezone(timedelta(hours=main_window.tz_offset))
        now = datetime.now(tz)
        
        # Обновляем главные часы в левой панели
        if hasattr(self, 'clock_lbl'):
            self.clock_lbl.setText(now.strftime("%H:%M:%S"))
        
        # Перебираем все виджеты внутри нашего макета со списком
        for i in range(self.tasks_list_layout.count()):
            item = self.tasks_list_layout.itemAt(i)
            if not item: continue
            
            card = item.widget()
            if isinstance(card, TaskCard):
                task = card.task
                
                if getattr(task, "status", "") == "Ожидание" and hasattr(task, "deadline"):
                    try:
                        task_dt = task.deadline.replace(tzinfo=tz)
                        
                        # --- МАГИЯ 4 ЭТАПА: Используем единый калькулятор ---
                        countdown_str = calculate_countdown_status(task_dt, now)
                        card.update_countdown(countdown_str)
                        
                    except ValueError:
                        pass
                else:
                    card.update_countdown("")

        # --- Динамическое обновление "Потрачено" в правой панели ---
        if self.current_task and getattr(self.current_task, "status", "") == "В работе":
            # Вызываем нашу единую функцию!
            _, spent_str = calculate_dynamic_time(self.current_task, main_window.tz_offset)
            
            deadline = getattr(self.current_task, 'deadline', None)
            d_str = deadline.strftime("%d.%m.%Y %H:%M") if deadline else "Не указан"
            
            self.det_info_lbl.setText(f"⏳ Дедлайн: {d_str}\n⏱ Потрачено: {spent_str}")
    
    def handle_card_click(self, task, modifiers):
        """Умная обработка кликов с поддержкой Shift и Ctrl"""
        all_cards = [self.tasks_list_layout.itemAt(i).widget() for i in range(self.tasks_list_layout.count()) if self.tasks_list_layout.itemAt(i) and self.tasks_list_layout.itemAt(i).widget()]
        tasks_list = [c.task for c in all_cards]
        
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # Снимаем или добавляем выделение
            if any(getattr(t, 'id', None) == getattr(task, 'id', None) for t in self.selected_tasks):
                self.selected_tasks = [t for t in self.selected_tasks if getattr(t, 'id', None) != getattr(task, 'id', None)]
            else:
                self.selected_tasks.append(task)
            self.last_clicked_task = task
        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            # Выделение диапазона
            if not self.last_clicked_task:
                self.selected_tasks = [task]
                self.last_clicked_task = task
            else:
                try:
                    idx1 = next(i for i, t in enumerate(tasks_list) if getattr(t, 'id', None) == getattr(self.last_clicked_task, 'id', None))
                    idx2 = next(i for i, t in enumerate(tasks_list) if getattr(t, 'id', None) == getattr(task, 'id', None))
                    start, end = min(idx1, idx2), max(idx1, idx2)
                    self.selected_tasks = tasks_list[start:end+1]
                except StopIteration:
                    self.selected_tasks = [task]
        else:
            # Обычный клик
            self.selected_tasks = [task]
            self.last_clicked_task = task
            
        # Обновляем визуал карточек
        for card in all_cards:
            is_sel = any(getattr(t, 'id', None) == getattr(card.task, 'id', None) for t in self.selected_tasks)
            card.set_selected(is_sel)
            
        # Обновляем правую панель
        if len(self.selected_tasks) == 1:
            self.show_task_details(self.selected_tasks[0])
        elif len(self.selected_tasks) > 1:
            self.show_multiple_selected()
        else:
            self.clear_details_panel()

    def show_multiple_selected(self):
        """Правая панель при выделении нескольких задач"""
        self.current_task = None
        self.det_client_lbl.setText(f"Выбрано задач: {len(self.selected_tasks)}")
        self.det_desc_lbl.setText("Групповые действия доступны через контекстное меню (правый клик по списку).")
        self.det_status_lbl.setText("")
        self.det_info_lbl.setText("")
        
        # Сбрасываем виджет
        self.task_details_widget.set_task(None)
        
        self.det_history.clear()
        
        # Отключаем нижние кнопки
        for btn in (self.btn_play, self.btn_success, self.btn_reschedule, self.btn_screenshot, self.btn_archive):
            btn.setEnabled(False)

    def update_action_buttons(self):
        if not self.current_task: return
        task_status = getattr(self.current_task, 'status', 'Ожидание')
        is_active = (task_status != "Завершено")
        
        # Проверяем выполнение чек-листа напрямую из объекта задачи
        subtasks = getattr(self.current_task, 'subtasks', [])
        all_done = True
        if subtasks:
            all_done = all(st.get('completed', False) or st.get('done', False) for st in subtasks if isinstance(st, dict))
                
        self.btn_play.setEnabled(task_status in ("Ожидание", "Время вышло"))
        self.btn_reschedule.setEnabled(is_active)
        self.btn_screenshot.setEnabled(is_active)
        
        self.btn_success.setEnabled((task_status == "В работе") and all_done)
        self.btn_archive.setEnabled(is_active and all_done)
    
    def refresh_data(self):
        # 1. Применяем тему через стандартизированный метод
        main_window = self.window()
        theme_name = getattr(main_window, 'current_theme', 'dark_fantasy') if main_window else 'dark_fantasy'
        from tabs.themes import get_theme_palette
        self.apply_theme(get_theme_palette(theme_name))
        
        # 2. Очищаем старые виджеты (осторожно с отступами!)
        while self.tasks_list_layout.count():
            child = self.tasks_list_layout.takeAt(0)
            if child.widget(): 
                child.widget().deleteLater()
                
        # 3. Получаем задачи
        tasks = getattr(self.task_repo, 'get_all', getattr(self.task_repo, 'get_all_tasks', lambda: []))()
        active_and_future_tasks = [t for t in tasks if getattr(t, 'status', '') != "Завершено"]

        # 4. Создаем новые карточки
        for task in active_and_future_tasks:
            card = TaskCard(task, parent=self)
            if any(getattr(task, 'id', None) == getattr(st, 'id', None) for st in getattr(self, 'selected_tasks', [])):
                card.set_selected(True)
                
            card.clicked.connect(self.handle_card_click)
            card.btn_action.clicked.connect(lambda checked, t=task: self.quick_action_clicked(t))
            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(lambda pos, c=card, t=task: self.show_card_context_menu(pos, c, t))
            self.tasks_list_layout.addWidget(card)
            
        if not active_and_future_tasks:
            empty_lbl = QLabel("Список задач пуст")
            empty_lbl.setStyleSheet("color: #777; font-size: 14px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tasks_list_layout.addWidget(empty_lbl)
            
        # 5. Восстанавливаем актуальный список выбранных
        self.selected_tasks = [t for t in active_and_future_tasks if any(getattr(t, 'id', None) == getattr(st, 'id', None) for st in getattr(self, 'selected_tasks', []))]
        
        if len(self.selected_tasks) == 1:
            self.show_task_details(self.selected_tasks[0])
        elif len(self.selected_tasks) > 1:
            self.show_multiple_selected()
        else:
            self.clear_details_panel()
    
    def show_task_details(self, task):
        self.current_task = task
        self.details_panel.setVisible(True)  # <--- Показываем правую панель, когда задача выбрана
        
        # Обновляем текстовые метки
        self.det_client_lbl.setText(str(getattr(task, 'client', 'Без клиента')))
        self.det_desc_lbl.setText(str(getattr(task, 'task', 'Без описания')))
        self.det_status_lbl.setText(f"[{getattr(task, 'status', 'Ожидание')}]")
        
        deadline = getattr(task, 'deadline', None)
        d_str = deadline.strftime("%d.%m.%Y %H:%M") if deadline else "Не указан"
        
        main_window = self.window()
        tz_offset = getattr(main_window, 'tz_offset', 3) if main_window else 3
        
        _, spent_str = calculate_dynamic_time(task, tz_offset)
        self.det_info_lbl.setText(f"⏳ Дедлайн: {d_str}\n⏱ Потрачено: {spent_str}")
        
        self.task_details_widget.set_task(task)
        
        # --- ЗАГРУЗКА ИСТОРИИ ИЗМЕНЕНИЙ ---
        history = getattr(task, "history", [])
        timeline_html = """
        <style>
            .timeline { font-family: 'Segoe UI', sans-serif; padding: 2px; }
            .event { margin-bottom: 10px; border-left: 2px solid #34495e; padding-left: 10px; position: relative; }
            .time { font-size: 11px; color: #95a5a6; font-weight: bold; }
            .action { font-size: 13px; color: #ecf0f1; margin-top: 2px; }
        </style>
        <div class="timeline">
        """

        for h in history:
            if hasattr(h, 'timestamp') and hasattr(h, 'action'):
                ts_str = h.timestamp.strftime('%d.%m.%Y %H:%M:%S') if isinstance(h.timestamp, datetime) else str(h.timestamp)
                action_text = h.action
            else:
                ts_str = ""
                action_text = str(h)

            marker = "⚪" 
            border_color = "#95a5a6"

            lower_action = action_text.lower()
            if "создан" in lower_action or "старт" in lower_action or "завершен" in lower_action or "успешн" in lower_action:
                marker, border_color = "🟢", "#2ecc71"
            elif "работу" in lower_action or "таймер" in lower_action:
                marker, border_color = "🔵", "#3498db"
            elif "перенос" in lower_action or "отложен" in lower_action:
                marker, border_color = "🟡", "#f1c40f"
            elif "скриншот" in lower_action or "файл" in lower_action:
                marker, border_color = "🟠", "#e67e22"
            elif "просроч" in lower_action or "ошибк" in lower_action or "вышло" in lower_action:
                marker, border_color = "🔴", "#e74c3c"

            time_part = f'<div class="time">{marker} {ts_str}</div>' if ts_str else f'<div class="time">{marker}</div>'
            timeline_html += f"""
            <div class="event" style="border-left-color: {border_color};">
                {time_part}
                <div class="action">{action_text}</div>
            </div>
            """

        timeline_html += "</div>"
        self.det_history.setHtml(timeline_html)
        
        # Обновляем кнопки действий
        self.update_action_buttons()
        
            
    def clear_details_panel(self):
        """Полностью сбрасывает и СКРЫВАЕТ правую панель, если задача не выбрана"""
        self.current_task = None
        self.details_panel.setVisible(False)  # <--- Скрываем правую панель полностью, когда ничего не выбрано
        
        self.det_client_lbl.setText("Выберите задачу")
        self.det_desc_lbl.setText("Здесь будет отображаться описание...")
        self.det_status_lbl.setText("")
        self.det_info_lbl.setText("")
        
        self.task_details_widget.set_task(None)
        self.det_history.clear()
        
    
    def quick_action_clicked(self, task_data):
        if not any(getattr(t, 'id', None) == getattr(task_data, 'id', None) for t in getattr(self, 'selected_tasks', [])):
            self.handle_card_click(task_data, Qt.KeyboardModifier.NoModifier)
            
        status = getattr(task_data, 'status', 'Ожидание')
        if status in ("Ожидание", "Время вышло"): 
            events.action_start_work.emit(task_data)
        elif status == "В работе": 
            events.action_mark_success.emit(task_data)
        else: 
            events.action_complete_task.emit(task_data)

    def show_card_context_menu(self, pos, card_widget, task_data):
        # Если кликнули мимо текущего выделения — выделяем только эту карточку
        if not any(getattr(t, 'id', None) == getattr(task_data, 'id', None) for t in getattr(self, 'selected_tasks', [])):
            self.handle_card_click(task_data, Qt.KeyboardModifier.NoModifier)
            
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { border-radius: 6px; font-family: 'Segoe UI'; font-size: 13px; } QMenu::item { padding: 8px 25px; margin: 2px 4px; border-radius: 4px; }")
        
        action_edit = menu.addAction("✏ Редактировать")
        action_delete = menu.addAction("🗑 Удалить")
        menu.addSeparator()
        
        # Если выделено несколько задач, прячем быстрые действия "В работу" (они только для одной)
        action_quick = None
        if len(self.selected_tasks) == 1:
            status = getattr(task_data, 'status', 'Ожидание')
            if status in ("Ожидание", "Время вышло"): action_quick = menu.addAction("▶ В работу")
            elif status == "В работе": action_quick = menu.addAction("✅ Успешно")
                
        selected_action = menu.exec(card_widget.mapToGlobal(pos))
        
        if selected_action == action_edit: 
            QTimer.singleShot(10, lambda: events.action_edit_task.emit(task_data))
        elif selected_action == action_delete:
            # Спрашиваем перед удалением прямо в интерфейсе
            from PyQt6.QtWidgets import QMessageBox
            if QMessageBox.question(self, 'Удаление', 'Точно удалить?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                QTimer.singleShot(10, lambda: events.action_delete_task.emit(task_data))
    
    def update_modern_calendar_tasks(self):
        self.modern_day_tasks.clear()
        selected_date = self.modern_calendar.selectedDate().toString("dd.MM.yyyy")
        tasks_found = False
        
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
                    has_activity_today = True
                    break
                    
            if is_current or is_history or has_activity_today:
                raw_status = getattr(data, "status", "Ожидание")
                if is_current and raw_status not in ("Успешно", "Завершено", "Выполнено"):
                    status = raw_status
                else:
                    status = f"Архив: {raw_status}" if raw_status in ("Успешно", "Завершено", "Выполнено") else "Архив: Выполнено"
                    
                if is_current and raw_status in ("Успешно", "Завершено", "Выполнено"):
                    status = raw_status
                    
                if history_time_str:
                    spent_str = f" | ⏱ {history_time_str}"
                else:
                    spent_seconds = getattr(data, 'time_spent', 0)
                    spent_str = f" | ⏱ {format_time_spent(spent_seconds)}" if spent_seconds > 0 else " | ⏱ 0м"
                    
                task_time = data.deadline.strftime("%H:%M") if hasattr(data, 'deadline') else ""
                task_client = getattr(data, 'client', '')
                task_desc = getattr(data, 'task', '')
                task_id = getattr(data, 'id', None)
                
                day_item = QListWidgetItem(
                    f"[{status}] {task_time} - {task_client}{spent_str}\nЗадача: {task_desc}"
                )
                day_item.setData(Qt.ItemDataRole.UserRole, task_id)
                self.modern_day_tasks.addItem(day_item)
                tasks_found = True
                
        if not tasks_found:
            self.modern_day_tasks.addItem("На этот день задач нет.")

    def load_task_from_modern_calendar(self, day_item):
        target_id = day_item.data(Qt.ItemDataRole.UserRole)
        if not target_id: return
        task_obj = self.task_repo.get_by_id(target_id)
        if task_obj:
            self.content_stack.setCurrentIndex(0)  # Возвращаемся на вкладку задач
            self.show_task_details(task_obj)
    def show_calendar_dev_menu(self, pos):
        main_win = self.window()
        if getattr(main_win, 'dev_mode', False):
            from tabs.dev_tools import show_dev_context_menu
            show_dev_context_menu(self.modern_day_tasks, pos, self.task_repo)
    
from tabs.events import register_workspace
register_workspace("Современный вид", ModernWorkspace)