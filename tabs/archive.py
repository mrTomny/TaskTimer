import re
from datetime import datetime
from tabs.logger import log
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt
from tabs.utils import format_time_spent, extract_spent_time_from_history
from tabs.models import Task, HistoryEvent

class ArchiveTab(QWidget):
    # ДОБАВЬ parent=None в скобки
    def __init__(self, parent=None): 
        # ПЕРЕДАЙ parent в super()
        super().__init__(parent)
        
        self.tasks_data = [] # Здесь будем хранить задачи, переданные извне
        
        self.layout = QVBoxLayout(self)

        # 1. Поле для поиска
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Начни вводить текст для поиска...")
        self.search_input.textChanged.connect(self.refresh_table) 
        self.layout.addWidget(self.search_input)

        # 2. Таблица с результатами
        self.table = QTableWidget()
        self.table.setColumnCount(4) 
        self.table.setHorizontalHeaderLabels(["Дата", "Клиент", "Задача", "Затрачено"])
        
        # ЗАПРЕТ НА РЕДАКТИРОВАНИЕ
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) 
        
        self.layout.addWidget(self.table)

    def update_data(self, tasks):
        """Этот метод будет вызываться из главного окна для передачи актуальных данных"""
        self.tasks_data = tasks
        self.refresh_table()

    def refresh_table(self):
        search_text = self.search_input.text().lower()
        self.table.setRowCount(0) 

        try:
            rows_to_display = []
            
            for task_obj in self.tasks_data:
                deadline_dt = getattr(task_obj, "deadline", None)
                main_date = deadline_dt.strftime("%d.%m.%Y") if isinstance(deadline_dt, datetime) else ""
                
                client = getattr(task_obj, "client", "")
                task_name = getattr(task_obj, "task", "")
                current_time_spent = getattr(task_obj, "time_spent", 0)
                status = getattr(task_obj, "status", "")
                history_logs = getattr(task_obj, "history", [])
                
                # --- СТАЛО: Вызываем функцию парсинга в одну строку ---
                fallback = main_date or datetime.now().strftime("%d.%m.%Y")
                spent_per_date = extract_spent_time_from_history(history_logs, fallback)

                # Формируем список дат для вывода
                all_completed_dates = set(spent_per_date.keys())
                
                # Добавляем даты завершения ТОЛЬКО если задача закрыта (отсекаем будущие)
                if status in ("Успешно", "Выполнено", "Завершено"):
                    if getattr(task_obj, "completed_dates", None):
                        for cd in task_obj.completed_dates:
                            all_completed_dates.add(cd)
                    elif main_date:
                        all_completed_dates.add(main_date)
                        
                # Если дат нет (задача в работе, но время еще не списывали) — пропускаем её
                if not all_completed_dates:
                    continue
                        
                # Формируем строки для архива
                for d in all_completed_dates:
                    spent_str = spent_per_date.get(d, "")
                    if not spent_str:
                        spent_str = format_time_spent(current_time_spent) if current_time_spent > 0 else "0м"
                        
                    rows_to_display.append((d, client, task_name, spent_str, task_obj))
            
            def get_sort_key(row_data):
                date_str = row_data[0]
                try:
                    return datetime.strptime(date_str, "%d.%m.%Y")
                except ValueError:
                    return datetime.min

            # Сортируем от новых к старым
            rows_to_display.sort(key=get_sort_key, reverse=True)
            
            # Теперь распаковываем 5 элементов, включая task_obj
            for date, client, task_name, spent_str, task_obj in rows_to_display:
                if search_text in task_name.lower() or search_text in date.lower() or search_text in client.lower():
                    row_position = self.table.rowCount()
                    self.table.insertRow(row_position)
                    
                    # Создаем ячейку для даты и прячем в нее объект задачи
                    item_date = QTableWidgetItem(date)
                    item_date.setData(Qt.ItemDataRole.UserRole, task_obj)
                    
                    self.table.setItem(row_position, 0, item_date)
                    self.table.setItem(row_position, 1, QTableWidgetItem(client)) 
                    self.table.setItem(row_position, 2, QTableWidgetItem(task_name))
                    self.table.setItem(row_position, 3, QTableWidgetItem(spent_str))
                    
        except Exception as e:
            log.error(f"Ошибка загрузки архива: {e}")
            
    def apply_theme(self, palette):
        """Применяет современную цветовую палитру к таблице архива"""
        bg_main = palette.get('menu_bg', '#1a1a1a')
        bg_comp = palette.get('cal_comp_bg', '#1a1a1a')
        bg_input = palette.get('history_bg', '#121212')
        fg_color = palette.get('menu_fg', '#c0c0c0')
        fg_input = palette.get('history_fg', '#b3b3b3')
        sel_color = palette.get('menu_sel', '#331414')
        border_color = palette.get('version', '#555555')
        accent_color = palette.get('in_progress', '#3498db')
        
        self.setStyleSheet(f"""
            ArchiveTab {{
                background-color: {bg_main};
            }}
            QLineEdit {{
                background-color: {bg_input};
                color: {fg_input};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 10px 12px;
                font-family: 'Segoe UI';
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {accent_color};
            }}
            QTableWidget {{
                background-color: {bg_comp};
                color: {fg_color};
                gridline-color: rgba(255, 255, 255, 0.05);
                border: 1px solid {border_color};
                border-radius: 8px;
                font-family: 'Segoe UI';
                font-size: 13px;
                selection-background-color: {sel_color};
            }}
            QHeaderView::section {{
                background-color: {bg_main};
                color: {fg_color};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {border_color};
                font-family: 'Segoe UI';
                font-weight: bold;
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 6px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            }}
            QTableWidget::item:selected {{
                background-color: {sel_color};
                color: {fg_color};
            }}
        """)
    
    def show_context_menu(self, pos):
        main_win = self.window()
        if getattr(main_win, 'dev_mode', False):
            from tabs.dev_tools import show_dev_context_menu
            show_dev_context_menu(self.table, pos, getattr(main_win, 'task_repo', None))