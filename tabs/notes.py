import re
import webbrowser
from tabs.logger import log
from tabs.models import Task, HistoryEvent
from tabs.events import events
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QTabWidget, 
                             QTabBar, QMessageBox, QInputDialog, QMenu)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


class LinkableTextEdit(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setToolTip("Удерживай Ctrl + Клик, чтобы открыть ссылку")

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            cursor = self.cursorForPosition(event.pos())
            block_text = cursor.block().text()
            pos_in_block = cursor.positionInBlock()
            
            urls = re.finditer(r'(https?://\S+|www\.\S+)', block_text)
            for match in urls:
                if match.start() <= pos_in_block <= match.end():
                    url = match.group(1).rstrip(r'.,!?)\]"') 
                    if url.startswith('www.'):
                        url = 'https://' + url
                    webbrowser.open(url)
                    break
                    
class NoteEditor(QWidget):
    def __init__(self, note_id, initial_text):
        super().__init__()
        self.note_id = note_id
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.text_edit = LinkableTextEdit()
        self.text_edit.setPlainText(initial_text)
        self.text_edit.setFont(QFont("Segoe UI", 12))
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_to_db)
        self.text_edit.textChanged.connect(lambda: self.save_timer.start(1000))

        # Слушаем изменения текста из других интерфейсов
        events.note_content_updated.connect(self.on_external_content_update)

    def save_to_db(self):
        text = self.text_edit.toPlainText()
        events.action_update_note_content.emit(self.note_id, text)

    def on_external_content_update(self, note_id, content):
        # Обновляем текст только если это та же заметка, но пользователь в ней НЕ печатает прямо сейчас (нет фокуса)
        if self.note_id == note_id and not self.text_edit.hasFocus():
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(content)
            self.text_edit.blockSignals(False)

class NotesManager(QTabWidget): 
    def __init__(self, get_notes_cb, parent=None):
        super().__init__(parent)
        self.get_notes_cb = get_notes_cb
        self.setFont(QFont("Segoe UI", 11))
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.delete_note)
        self.tabBarDoubleClicked.connect(self.rename_note)
        
        tab_bar = self.tabBar()
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self.show_context_menu)
        self.tabBar().tabBarClicked.connect(self.on_tab_clicked)

        events.notes_changed.connect(self.reload_notes)

        self.load_notes()
        self.add_plus_tab()

    def add_plus_tab(self):
        self.plus_tab_widget = QWidget()
        idx = self.addTab(self.plus_tab_widget, "➕ Новая заметка")
        self.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, None)

    def on_tab_clicked(self, index):
        if index == self.count() - 1:
            events.action_add_note.emit("Новая заметка", "")

    def reload_notes(self):
        # 1. Запоминаем ID текущей открытой заметки перед перерисовкой
        current_widget = self.currentWidget()
        current_note_id = getattr(current_widget, 'note_id', None)

        self.blockSignals(True)
        self.clear()
        self.load_notes()
        self.add_plus_tab()
        self.blockSignals(False)

        # 2. Восстанавливаем выбор на ту же самую заметку, если она еще существует
        if current_note_id is not None:
            for i in range(self.count()):
                w = self.widget(i)
                if getattr(w, 'note_id', None) == current_note_id:
                    self.setCurrentIndex(i)
                    break

    def load_notes(self):
        if not getattr(self, 'get_notes_cb', None): return
        for note_id, title, content in self.get_notes_cb():
            editor = NoteEditor(note_id, content)
            self.addTab(editor, title)

    def delete_note(self, index):
        if index == self.count() - 1: return
        editor_widget = self.widget(index)
        
        if QMessageBox.question(self, 'Удаление', 'Точно удалить эту заметку?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            events.action_delete_note.emit(editor_widget.note_id)

    def rename_note(self, index):
        if index < 0 or index == self.count() - 1: return
        old_title = self.tabText(index)
        new_title, ok = QInputDialog.getText(self, 'Переименование', 'Введите новое название:', text=old_title)
        
        if ok and new_title.strip():
            cleaned_title = new_title.strip()
            self.setTabText(index, cleaned_title)
            events.action_update_note_title.emit(self.widget(index).note_id, cleaned_title)

    def show_context_menu(self, position):
        tab_bar = self.tabBar()
        index = tab_bar.tabAt(position)
        if index >= 0 and index != self.count() - 1:
            menu = QMenu(self)
            rename_act = menu.addAction("Изменить")
            delete_act = menu.addAction("Удалить")
            action = menu.exec(tab_bar.mapToGlobal(position))
            
            if action == rename_act: self.rename_note(index)
            elif action == delete_act: self.delete_note(index)