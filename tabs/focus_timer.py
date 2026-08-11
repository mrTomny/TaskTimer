from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTextEdit, QListWidget, QListWidgetItem
from PyQt6.QtCore import QTimer, Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont


class FocusTimerWidget(QWidget):
    def __init__(self, total_seconds=1500, parent=None):
        super().__init__(parent)
        self.total_seconds = total_seconds
        self.remaining_seconds = total_seconds
        self.is_running = False
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        
        self.setMinimumSize(220, 220)

    def start_timer(self):
        if not self.is_running:
            self.is_running = True
            self.timer.start(1000)

    def pause_timer(self):
        if self.is_running:
            self.is_running = False
            self.timer.stop()

    def reset_timer(self, seconds=None):
        self.pause_timer()
        if seconds is not None:
            self.total_seconds = seconds
        self.remaining_seconds = self.total_seconds
        self.update()

    def update_timer(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.update()
        else:
            self.pause_timer()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        side = min(width, height)
        
        rect = QRectF(
            (width - side) / 2 + 15, 
            (height - side) / 2 + 15, 
            side - 30, 
            side - 30
        )
        
        bg_pen = QPen(QColor(60, 60, 65), 10, Qt.PenStyle.SolidLine)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawEllipse(rect)
        
        if self.total_seconds > 0:
            progress = self.remaining_seconds / self.total_seconds
            span_angle = int(-progress * 360 * 16)
        else:
            span_angle = 0
            
        progress_pen = QPen(QColor(0, 122, 204), 10, Qt.PenStyle.SolidLine)
        progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(progress_pen)
        painter.drawArc(rect, 90 * 16, span_angle)
        
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        time_text = f"{minutes:02d}:{seconds:02d}"
        
        painter.setPen(QColor(240, 240, 240))
        painter.setFont(QFont("Segoe UI", int(side / 8), QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, time_text)


class FocusTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(15, 15, 15, 15)
        
        self.card_frame = QFrame(self)

        # Главная карточка, объединяющая таймер и все информационные блоки
        self.card_frame = QFrame()
        self.card_frame.setStyleSheet("""
            QFrame#FocusCard {
                background-color: #161616;
                border: 1px solid #282828;
                border-radius: 12px;
            }
        """)
        self.card_frame.setObjectName("FocusCard")
        self.card_frame.setFixedSize(420, 700)

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(15, 12, 15, 12) 
        card_layout.setSpacing(10)

        # --- 1. ТАЙМЕР СВЕРХУ ---
        timer_layout = QHBoxLayout()
        timer_layout.addStretch()
        
        self.timer_widget = FocusTimerWidget(parent=self.card_frame) 
        self.timer_widget.setFixedSize(150, 150)
        timer_layout.addWidget(self.timer_widget)
        
        timer_layout.addStretch()
        card_layout.addLayout(timer_layout)
        card_layout.addWidget(self._create_separator())

        # --- 2. ИНФОРМАЦИЯ О КЛИЕНТЕ И ЗАДАЧЕ ---
        info_container = QWidget(self.card_frame)
        info_container.setStyleSheet("background: transparent;")
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)

        self.lbl_client = QLabel("👤 Клиент не выбран", info_container)
        self.lbl_client.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_client.setStyleSheet("color: #FFFFFF; background: transparent;")

        self.lbl_task = QLabel("📌 Задача не выбрана", info_container)
        self.lbl_task.setFont(QFont("Segoe UI", 11))
        self.lbl_task.setStyleSheet("color: #CCCCCC; background: transparent;")

        deadline_container = QHBoxLayout()
        deadline_container.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_deadline_title = QLabel("⏳ До дедлайна:", info_container)
        self.lbl_deadline_title.setFont(QFont("Segoe UI", 10))
        self.lbl_deadline_title.setStyleSheet("color: #888888; background: transparent;")

        self.lbl_deadline_val = QLabel("—", info_container)
        self.lbl_deadline_val.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_deadline_val.setStyleSheet("color: #3498db; background: transparent;")
        
        deadline_container.addWidget(self.lbl_deadline_title)
        deadline_container.addWidget(self.lbl_deadline_val)
        deadline_container.addStretch()

        info_layout.addWidget(self.lbl_client)
        info_layout.addWidget(self.lbl_task)
        info_layout.addLayout(deadline_container)

        card_layout.addWidget(info_container)
        card_layout.addWidget(self._create_separator())

        # --- 3. ЧЕК-ЛИСТ СЕАНСА ---
        subtasks_container = QWidget(self.card_frame)
        subtasks_container.setStyleSheet("background: transparent;")
        sub_layout = QVBoxLayout(subtasks_container)
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(6)

        sub_title = QLabel("📋 Чек-лист сеанса:", subtasks_container)
        sub_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        sub_title.setStyleSheet("color: #AAAAAA; background: transparent;")
        sub_layout.addWidget(sub_title)

        self.focus_subtasks_list = QListWidget(subtasks_container)
        self.focus_subtasks_list.setFont(QFont("Segoe UI", 10))
        self.focus_subtasks_list.setMaximumHeight(120)
        self.focus_subtasks_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                color: #FFFFFF;
                padding: 4px;
            }
            QListWidget::item {
                padding: 3px;
            }
        """)
        sub_layout.addWidget(self.focus_subtasks_list)

        card_layout.addWidget(subtasks_container)
        card_layout.addWidget(self._create_separator())

        # --- 4. ЗАМЕТКИ ---
        notes_container = QWidget(self.card_frame)
        notes_container.setStyleSheet("background: transparent;")
        notes_layout = QVBoxLayout(notes_container)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(6)

        notes_title = QLabel("📝 Заметки:", notes_container)
        notes_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        notes_title.setStyleSheet("color: #AAAAAA; background: transparent;")
        notes_layout.addWidget(notes_title)

        self.quick_notes_edit = QTextEdit(notes_container)
        self.quick_notes_edit.setPlaceholderText("Запишите сюда промежуточные мысли или идеи...")
        self.quick_notes_edit.setFont(QFont("Segoe UI", 10))
        self.quick_notes_edit.setMaximumHeight(130)
        self.quick_notes_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #FFFFFF;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        notes_layout.addWidget(self.quick_notes_edit)

        card_layout.addWidget(notes_container)

        # Центрируем всю карточку на вкладке
        center_hbox = QHBoxLayout()
        center_hbox.addStretch()
        center_hbox.addWidget(self.card_frame)
        center_hbox.addStretch()

        center_vbox = QVBoxLayout()
        center_vbox.addStretch()
        center_vbox.addLayout(center_hbox)
        center_vbox.addStretch()

        outer_layout.addLayout(center_vbox)

    def _create_separator(self):
        line = QFrame(self.card_frame) # <--- ДОБАВЛЕН self.card_frame вместо пустых скобок
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet("background-color: #262626; max-height: 1px; border: none;")
        return line

    def set_active_task(self, task_data):
        if not task_data:
            # Если передали None (задача не выбрана)
            self.lbl_client.setText("👤 Клиент не выбран")
            self.lbl_task.setText("📌 Задача не выбрана")
        elif isinstance(task_data, str):
            # Если передали готовую строку из TaskTimer.py
            if " — " in task_data:
                # Разрезаем строку на клиента и задачу по разделителю " — "
                client, task = task_data.split(" — ", 1)
                self.lbl_client.setText(f"👤 {client}")
                self.lbl_task.setText(f"📌 {task}")
            else:
                # На случай, если прилетел текст без разделителя
                self.lbl_client.setText("👤 Активная задача")
                self.lbl_task.setText(f"📌 {task_data}")
        else:
            # На случай, если туда всё же прилетит словарь
            client_name = task_data.get("client_name", "Клиент не выбран")
            task_name = task_data.get("task_name", "Без описания")
            self.lbl_client.setText(f"👤 {client_name}")
            self.lbl_task.setText(f"📌 {task_name}")