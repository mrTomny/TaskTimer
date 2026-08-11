from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QListWidget, QListWidgetItem, 
                             QLineEdit, QPushButton, QLabel, QMenu)
from PyQt6.QtCore import Qt, QTimer
from tabs.events import events

class TaskDetailsWidget(QWidget):
    def __init__(self, parent=None): # УБРАЛИ task_repo
        super().__init__(parent)
        self.current_task = None
        
        self.notes_timer = QTimer(self)
        self.notes_timer.setSingleShot(True)
        self.notes_timer.timeout.connect(self._save_notes)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Чек-лист (Подзадачи) ---
        self.subtasks_label = QLabel("Чек-лист:")
        layout.addWidget(self.subtasks_label)
        
        self.subtasks_list = QListWidget()
        self.subtasks_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subtasks_list.customContextMenuRequested.connect(self.show_subtasks_menu)
        self.subtasks_list.itemChanged.connect(self._save_subtasks) 
        layout.addWidget(self.subtasks_list)
        
        # Поле добавления подзадачи
        add_subtask_layout = QHBoxLayout()
        self.subtask_input = QLineEdit()
        self.subtask_input.setPlaceholderText("Добавить шаг (Enter)...")
        self.subtask_input.returnPressed.connect(self.add_subtask)
        
        self.btn_add_subtask = QPushButton("➕")
        self.btn_add_subtask.clicked.connect(self.add_subtask)
        
        add_subtask_layout.addWidget(self.subtask_input)
        add_subtask_layout.addWidget(self.btn_add_subtask)
        layout.addLayout(add_subtask_layout)
        
        # --- Заметки ---
        self.notes_label = QLabel("Заметки:")
        layout.addWidget(self.notes_label)
        
        # Если у вас используется LinkableTextEdit, замените QTextEdit на него
        self.notes_edit = QTextEdit()
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        layout.addWidget(self.notes_edit)

    def set_task(self, task):
        """Загружает данные задачи в виджет и обновляет UI"""
        self.current_task = task
        if not task:
            self.subtasks_list.clear()
            self.notes_edit.clear()
            self.setEnabled(False)
            return
            
        self.setEnabled(True)
        
        # Блокируем сигналы, чтобы заполнение списков не триггерило автосохранение
        self.subtasks_list.blockSignals(True)
        self.notes_edit.blockSignals(True)
        
        self.notes_edit.setPlainText(getattr(task, 'notes', ''))
        
        self.subtasks_list.clear()
        subtasks = getattr(task, 'subtasks', [])
        for st in subtasks:
            item = QListWidgetItem(st.get('text', ''))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            state = Qt.CheckState.Checked if st.get('completed', False) else Qt.CheckState.Unchecked
            item.setCheckState(state)
            self.subtasks_list.addItem(item)
            
        self.notes_edit.blockSignals(False)
        self.subtasks_list.blockSignals(False)

    def _on_notes_changed(self):
        # При каждом вводе символа таймер сбрасывается
        self.notes_timer.start(1000)

    def _save_notes(self):
        if not self.current_task: return
        new_notes = self.notes_edit.toPlainText()
        if getattr(self.current_task, 'notes', '') != new_notes:
            self.current_task.notes = new_notes
            # Отправляем сигнал вместо прямого сохранения
            events.action_update_task_notes.emit(getattr(self.current_task, 'id', None), new_notes)

    def add_subtask(self):
        if not self.current_task: return
        text = self.subtask_input.text().strip()
        if not text: return
        
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
        item.setCheckState(Qt.CheckState.Unchecked)
        
        self.subtasks_list.blockSignals(True)
        self.subtasks_list.addItem(item)
        self.subtasks_list.blockSignals(False)
        
        self.subtask_input.clear()
        self._save_subtasks()

    def _save_subtasks(self):
        if not self.current_task: return
        
        new_subtasks = []
        for i in range(self.subtasks_list.count()):
            item = self.subtasks_list.item(i)
            new_subtasks.append({
                'text': item.text(),
                'completed': item.checkState() == Qt.CheckState.Checked
            })
            
        self.current_task.subtasks = new_subtasks
        # Отправляем сигнал вместо прямого сохранения
        events.action_update_subtasks.emit(getattr(self.current_task, 'id', None), new_subtasks)
        
    def show_subtasks_menu(self, pos):
        item = self.subtasks_list.itemAt(pos)
        if not item: return
        
        menu = QMenu(self)
        del_action = menu.addAction("Удалить подзадачу")
        action = menu.exec(self.subtasks_list.mapToGlobal(pos))
        
        if action == del_action:
            self.subtasks_list.takeItem(self.subtasks_list.row(item))
            self._save_subtasks()