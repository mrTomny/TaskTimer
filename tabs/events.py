from PyQt6.QtCore import QObject, pyqtSignal


class GlobalEventBus(QObject):
    # --- Сигналы уровня данных ---
    task_added = pyqtSignal(object)       
    task_updated = pyqtSignal(object)     
    task_deleted = pyqtSignal(str)        
    
    # --- Глобальные сигналы UI ---
    data_changed = pyqtSignal()           
    timer_tick = pyqtSignal()             
    
    # --- Действия контроллера состояний (От UI к Контроллеру) ---
    action_start_work = pyqtSignal(object)       
    action_mark_success = pyqtSignal(object)     
    action_complete_task = pyqtSignal(object)    
    action_delete_task = pyqtSignal(object)      
    
    # --- НОВЫЕ КОМАНДЫ (Чистая модификация базы данных) ---
    action_add_task = pyqtSignal(dict)                # Передаем словарь с данными новой задачи
    action_save_edit_task = pyqtSignal(str, object)   # Передаем ID задачи и словарь новых данных
    action_save_reschedule = pyqtSignal(str, object)  # Передаем ID задачи и новый объект datetime
    action_change_color = pyqtSignal(str, str)        # Передаем ID задачи и HEX цвета
    action_save_screenshot = pyqtSignal(str, str)     # Передаем ID задачи и путь к файлу
    
    # --- Сигналы для открытия диалоговых окон (от кнопок к UI) ---
    action_reschedule_task = pyqtSignal(object)  
    action_screenshot = pyqtSignal(object)       
    action_edit_task = pyqtSignal(object)        
    
    # --- Сохранение деталей задачи (без прерывания фокуса UI) ---
    action_update_task_notes = pyqtSignal(str, str)     # Передает: ID задачи, новый текст заметок
    action_update_subtasks = pyqtSignal(str, list)      # Передает: ID задачи, новый список чек-листа

    # --- ЗАМЕТКИ (Отвязка от БД) ---
    action_add_note = pyqtSignal(str, str)             # title, content
    action_update_note_content = pyqtSignal(int, str)  # id, content
    action_update_note_title = pyqtSignal(int, str)    # id, title
    action_delete_note = pyqtSignal(int)               # id
    notes_changed = pyqtSignal()                       # Сигнал для перерисовки вкладок
    
    # --- ШАБЛОНЫ (Отвязка от БД) ---
    action_add_template = pyqtSignal(str, str, float, str)      # name, task_text, hours, color
    action_edit_template = pyqtSignal(int, str, str, float, str) # id, name, task_text, hours, color
    action_delete_template = pyqtSignal(int)                    # id
    templates_changed = pyqtSignal()
    
    note_content_updated = pyqtSignal(int, str)  # note_id, новый текст для синхронизации без сброса фокуса
    
    # --- СМЕНА ИНТЕРФЕЙСА ---
    action_switch_ui_mode = pyqtSignal(int)  # Сигнал-запрос (передает индекс: 0 или 1)
    ui_mode_changed = pyqtSignal(int)        # Сигнал-уведомление (интерфейс успешно изменен)
    
events = GlobalEventBus()

# ==========================================
# РЕЕСТР ИНТЕРФЕЙСОВ (АВТОМАТИЗАЦИЯ)
# ==========================================
REGISTERED_WORKSPACES = []

def register_workspace(name, cls_ref):
    """Функция для автоматической регистрации экранов в системе"""
    REGISTERED_WORKSPACES.append({"name": name, "class": cls_ref})
    
    
