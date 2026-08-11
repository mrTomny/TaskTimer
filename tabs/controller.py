from PyQt6.QtCore import QObject, pyqtSignal, QThread
from datetime import datetime, timezone, timedelta
import time
from tabs.logger import log
from tabs.events import events
from tabs.services import TaskService
from tabs.utils import NotificationService
from tabs.models import Task

class BackgroundClockThread(QThread):
    def run(self):
        while True:
            time.sleep(1)
            try:
                events.timer_tick.emit()
            except RuntimeError:
                # Если C++ объект шины был удален при выходе из программы, просто гасим поток
                break

class AppController(QObject):
    task_started = pyqtSignal(str, object, object) 
    task_stopped = pyqtSignal()
    
    def __init__(self, task_repo, db_manager, get_tz_offset_cb):
        super().__init__()
        self.task_repo = task_repo
        self.db_manager = db_manager  # Сохраняем менеджер базы данных
        self.get_tz_offset = get_tz_offset_cb
        
        self.active_task_name = None
        self.task_start_dt = None
        self.task_end_dt = None
        
        self.clock_thread = BackgroundClockThread()
        self.clock_thread.start()

        # ПОДПИСКА НА ДЕЙСТВИЯ С СОСТОЯНИЯМИ
        events.action_start_work.connect(self.handle_start_work)
        events.action_mark_success.connect(self.handle_mark_success)
        events.action_complete_task.connect(self.handle_complete_task)
        events.action_delete_task.connect(self.handle_delete_task)
        
        # ПОДПИСКА НА ИЗМЕНЕНИЕ ДАННЫХ В БАЗЕ 
        events.action_add_task.connect(self.handle_add_task)
        events.action_save_edit_task.connect(self.handle_save_edit)
        events.action_save_reschedule.connect(self.handle_save_reschedule)
        events.action_change_color.connect(self.handle_change_color)
        events.action_save_screenshot.connect(self.handle_save_screenshot)
        events.action_update_task_notes.connect(self.handle_update_task_notes)
        events.action_update_subtasks.connect(self.handle_update_subtasks)
        
        # ПОДПИСКА НА ЗАМЕТКИ И ШАБЛОНЫ
        events.action_add_note.connect(self.handle_add_note)
        events.action_update_note_content.connect(self.handle_update_note_content)
        events.action_update_note_title.connect(self.handle_update_note_title)
        events.action_delete_note.connect(self.handle_delete_note)
        
        events.action_add_template.connect(self.handle_add_template)
        events.action_edit_template.connect(self.handle_edit_template)
        events.action_delete_template.connect(self.handle_delete_template)
        
        # Подписка на смену интерфейса
        events.action_switch_ui_mode.connect(self.handle_switch_ui_mode)

    # === ЛОГИКА СОСТОЯНИЙ ТАЙМЕРА ===
    def handle_start_work(self, task):
        if not task: return
        NotificationService.stop_sound()
        db_task = self.task_repo.get_by_id(getattr(task, 'id', None))
        if not db_task: return

        TaskService.start_work(db_task, self.get_tz_offset())
        self.task_repo.update(db_task)
        
        current_tz = timezone(timedelta(hours=self.get_tz_offset()))
        self.active_task_name = f"{getattr(db_task, 'client', 'Без клиента')} — {getattr(db_task, 'task', 'Без названия')}"
        self.task_start_dt = datetime.now(current_tz)
        self.task_end_dt = getattr(db_task, 'deadline', None)
        
        log.info(f"[AppController] Взята в работу: '{self.active_task_name}'")
        self.task_started.emit(self.active_task_name, self.task_start_dt, self.task_end_dt)
        events.data_changed.emit()

    def handle_mark_success(self, task):
        if not task: return
        NotificationService.stop_sound()
        db_task = self.task_repo.get_by_id(getattr(task, 'id', None))
        if db_task:
            TaskService.mark_success(db_task)
            self.task_repo.update(db_task)
            self.stop_task()
            events.data_changed.emit()

    def handle_complete_task(self, task):
        if not task: return
        NotificationService.stop_sound()
        db_task = self.task_repo.get_by_id(getattr(task, 'id', None))
        if db_task:
            TaskService.complete_task(db_task)
            self.task_repo.update(db_task)
            self.stop_task()
            events.data_changed.emit()

    def handle_delete_task(self, task):
        if not task: return
        NotificationService.stop_sound()
        task_id = getattr(task, 'id', None)
        db_task = self.task_repo.get_by_id(task_id)
        if db_task:
            if self.active_task_name == f"{getattr(db_task, 'client', '')} — {getattr(db_task, 'task', '')}":
                self.stop_task()
            self.task_repo.delete(task_id)
            events.data_changed.emit()

    # === НОВАЯ ЛОГИКА ИЗМЕНЕНИЯ ДАННЫХ ===
    def handle_add_task(self, data_dict):
        try:
            combined_dt = datetime.strptime(f"{data_dict['date']} {data_dict['time']}", "%d.%m.%Y %H:%M")
        except ValueError:
            combined_dt = datetime.now()

        new_task = Task(
            client=data_dict.get('client', ''),
            task=data_dict.get('task', ''),
            deadline=combined_dt,
            color=data_dict.get('color', ''),
            subtasks=data_dict.get('subtasks', [])
        )
        self.task_repo.add(new_task)
        events.data_changed.emit()

        if data_dict.get('start_immediately', False):
            self.handle_start_work(new_task)

    def handle_save_edit(self, task_id, raw_data):
        db_task = self.task_repo.get_by_id(task_id)
        if not db_task: return
        
        if isinstance(raw_data, dict):
            db_task.client = raw_data.get("client", db_task.client)
            db_task.task = raw_data.get("task", db_task.task)
            d_str, t_str = raw_data.get("date", ""), raw_data.get("time", "")
            if d_str and t_str:
                try:
                    new_dt = datetime.strptime(f"{d_str} {t_str}", "%d.%m.%Y %H:%M")
                    if new_dt > db_task.deadline:
                        db_task.status = "Ожидание"
                    db_task.deadline = new_dt
                except Exception: pass
            db_task.color = raw_data.get("color", db_task.color)
        
        db_task.history.append(TaskService.generate_history_log("Отредактированы данные контракта"))
        self.task_repo.update(db_task)
        events.data_changed.emit()

    def handle_save_reschedule(self, task_id, new_dt):
        db_task = self.task_repo.get_by_id(task_id)
        if db_task:
            TaskService.reschedule_task(db_task, new_dt)
            self.task_repo.update(db_task)
            events.data_changed.emit()

    def handle_change_color(self, task_id, color_hex):
        db_task = self.task_repo.get_by_id(task_id)
        if db_task:
            db_task.color = color_hex
            self.task_repo.update(db_task)
            events.data_changed.emit()

    def handle_save_screenshot(self, task_id, file_path):
        db_task = self.task_repo.get_by_id(task_id)
        if db_task and file_path:
            new_note = f"\n[Скриншот-отчет: {file_path}]"
            db_task.notes = (getattr(db_task, 'notes', '') + new_note).strip()
            db_task.history.append(TaskService.generate_history_log("Прикреплен скриншот"))
            self.task_repo.update(db_task)
            events.data_changed.emit()

    def stop_task(self):
        if not self.active_task_name: return
        log.info(f"[AppController] Задача остановлена: '{self.active_task_name}'")
        self.active_task_name = None
        self.task_start_dt = None
        self.task_end_dt = None
        self.task_stopped.emit()

    def has_active_task(self):
        return self.active_task_name is not None
        
    def handle_update_task_notes(self, task_id, notes_text):
        db_task = self.task_repo.get_by_id(task_id)
        if db_task:
            db_task.notes = notes_text
            self.task_repo.update(db_task)
            # ВАЖНО: Мы НЕ вызываем events.data_changed.emit() здесь!
            # Иначе при каждом нажатии клавиши весь UI будет перерисовываться, сбрасывая фокус ввода.

    def handle_update_subtasks(self, task_id, subtasks_list):
        db_task = self.task_repo.get_by_id(task_id)
        if db_task:
            db_task.subtasks = subtasks_list
            self.task_repo.update(db_task)
    
    # --- ЧТЕНИЕ ДАННЫХ ДЛЯ UI ---
    def get_notes(self):
        return self.db_manager.get_notes()
        
    def get_templates(self):
        return self.db_manager.get_templates()

    # --- ОБРАБОТЧИКИ ЗАМЕТОК ---
    def handle_add_note(self, title, content):
        self.db_manager.add_note(title, content)
        events.notes_changed.emit() # Говорим UI перерисоваться
        
    def handle_update_note_content(self, note_id, content):
        self.db_manager.update_note_content(note_id, content)
        # Рассылаем сигнал остальным открытым редакторам этой заметки
        events.note_content_updated.emit(note_id, content)
        
    def handle_update_note_title(self, note_id, title):
        self.db_manager.update_note_title(note_id, title)
        events.notes_changed.emit()
        
    def handle_delete_note(self, note_id):
        self.db_manager.delete_note(note_id)
        events.notes_changed.emit()

    # --- ОБРАБОТЧИКИ ШАБЛОНОВ ---
    def handle_add_template(self, name, task_text, hours, color):
        self.db_manager.add_template(name, task_text, hours, color)
        events.templates_changed.emit()
        
    def handle_edit_template(self, t_id, name, task_text, hours, color):
        self.db_manager.update_template(t_id, name, task_text, hours, color)
        events.templates_changed.emit()
        
    def handle_delete_template(self, t_id):
        self.db_manager.delete_template(t_id)
        events.templates_changed.emit()
    
    def handle_switch_ui_mode(self, mode_index):
        """
        Централизованная логика смены интерфейса.
        Здесь можно добавить дополнительные системные действия перед переключением.
        """
        ui_names = {0: "Классический", 1: "Современный"}
        log.info(f"[AppController] Запрос на смену интерфейса: {ui_names.get(mode_index, 'Неизвестный')}")
        
        # Даем команду главному окну и всем виджетам переключиться
        events.ui_mode_changed.emit(mode_index)
        
        # Заставляем интерфейсы обновить данные под новый вид
        events.data_changed.emit()