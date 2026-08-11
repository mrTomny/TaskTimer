from PyQt6.QtWidgets import QMenu, QMessageBox
from PyQt6.QtCore import Qt
from tabs.logger import log
from tabs.events import events

def show_dev_context_menu(widget, pos, task_repo):
    """Отображает скрытое меню разработчика."""
    item = widget.itemAt(pos)
    if not item: return

    # Достаем данные (в календаре это ID задачи, в архиве - сам объект)
    data = item.data(Qt.ItemDataRole.UserRole)
    if not data: return
    
    task_id = data if isinstance(data, str) else getattr(data, 'id', None)
    task_obj = task_repo.get_by_id(task_id)
    
    if not task_obj: return

    menu = QMenu(widget)
    menu.setStyleSheet("""
        QMenu { background-color: #2b2b2b; color: white; border: 1px solid #444; border-radius: 6px; font-family: 'Segoe UI'; font-size: 13px; }
        QMenu::item { padding: 8px 20px; border-radius: 4px; }
        QMenu::item:selected { background-color: #e74c3c; }
    """)

    delete_action = menu.addAction("⚠️ DEV: Удалить задачу навсегда")
    action = menu.exec(widget.mapToGlobal(pos))

    if action == delete_action:
        task_name = getattr(task_obj, 'task', 'Без названия')
        reply = QMessageBox.warning(
            widget,
            "Режим разработчика",
            f"Точно удалить задачу «{task_name}» навсегда?\nЭто действие нельзя отменить.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                task_repo.delete(task_id)
                log.info(f"[DEV TOOLS] Задача {task_id} удалена разработчиком.")
                # Глобальный сигнал заставит все интерфейсы обновиться автоматически!
                events.data_changed.emit() 
            except Exception as e:
                QMessageBox.critical(widget, "Ошибка", f"Не удалось удалить:\n{e}")