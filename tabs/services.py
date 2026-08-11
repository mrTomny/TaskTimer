import base64
import urllib.request
import os
import sys
import subprocess
import json
import calendar
from datetime import datetime, timedelta, timezone
from tabs.logger import log


class SettingsService:
    def __init__(self, settings_file):
        self.settings_file = settings_file
        # Дефолтные настройки программы
        self.default_settings = {
            "tz_offset": 3,
            "sound_type": "system",
            "sound_path": "",
            "screenshots_dir": "",
            "show_exit_warning": True,
            "current_theme": "dark_fantasy",
            "window_geometry": "",
            "window_state": "",
            "mini_geometry": "",
            "mini_player_style": "circular",
            "supabase_url": "",
            "supabase_key": "",
            "cloud_type_idx": 0,
            "auto_backup": False,
            "dev_mode": False
        }

    def load(self):
        """Загружает настройки из файла. Если файла нет или он поврежден — возвращает дефолтные."""
        if not os.path.exists(self.settings_file):
            return self.default_settings.copy()
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Объединяем загруженные данные с дефолтными, чтобы избежать ошибок при новых ключах
                settings = self.default_settings.copy()
                settings.update(data)
                return settings
        except Exception as e:
            log.error(f"Ошибка загрузки настроек: {e}")
            return self.default_settings.copy()

    def save(self, settings_dict):
        """Сохраняет переданный словарь настроек в файл."""
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings_dict, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log.error(f"Ошибка сохранения настроек: {e}")


class TaskService:
    @staticmethod
    def start_timer(task):
        if not task.active_since:
            task.active_since = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def stop_timer(task):
        if task.active_since:
            try:
                start_dt = datetime.strptime(task.active_since, "%Y-%m-%d %H:%M:%S")
                diff_seconds = int((datetime.now() - start_dt).total_seconds())
                if diff_seconds > 0:
                    task.time_spent += diff_seconds
            except ValueError:
                pass
            task.active_since = ""
            
    @staticmethod
    def start_work(task, tz_offset: int):
        """Переводит задачу в работу и фиксирует текущее время как новый дедлайн."""
        current_tz = timezone(timedelta(hours=tz_offset))
        current_dt = datetime.now(current_tz)
        
        old_dt_str = task.deadline.strftime("%d.%m.%Y %H:%M") if hasattr(task, 'deadline') else ""
        
        task.status = "В работе"
        task.deadline = current_dt.replace(tzinfo=None)
        
        TaskService.start_timer(task)
        
        new_dt_str = task.deadline.strftime("%d.%m.%Y %H:%M")
        task.history.append(TaskService.generate_history_log(
            f"Взято в работу. Дедлайн изменен с {old_dt_str} на {new_dt_str}"
        ))

    @staticmethod
    def mark_success(task):
        """Завершает активный этап задачи, списывает время и переносит дедлайн на месяц."""
        from tabs.utils import format_time_spent
        
        TaskService.stop_timer(task)
        
        spent_seconds = getattr(task, 'time_spent', 0)
        spent_str = f" [Затрачено: {format_time_spent(spent_seconds)}]" if spent_seconds > 0 else ""
        if spent_seconds > 0:
            task.time_spent = 0
            
        old_date_str = task.deadline.strftime("%d.%m.%Y %H:%M")
        
        # Безусловный перенос на месяц вперед
        next_date_str = TaskService.calculate_next_month_date(task.deadline.strftime("%d.%m.%Y"))
        task.deadline = datetime.strptime(f"{next_date_str} {task.deadline.strftime('%H:%M')}", "%d.%m.%Y %H:%M")
        
        # Обязательно возвращаем в статус Ожидания, чтобы интерфейс разблокировал кнопки
        task.status = "Ожидание" 
            
        new_date_str = task.deadline.strftime("%d.%m.%Y %H:%M")
        task.history.append(TaskService.generate_history_log(
            f"Этап завершен{spent_str}. Авто-перенос дедлайна с {old_date_str} на {new_date_str}"
        ))

    @staticmethod
    def calculate_next_month_date(date_str):
        """Безопасно прибавляет 1 месяц к дате с учетом выходных (перенос на пятницу)"""
        import calendar
        from datetime import timedelta
        
        try:
            dt = datetime.strptime(date_str, "%d.%m.%Y")
            if dt.month == 12:
                new_year = dt.year + 1
                new_month = 1
            else:
                new_year = dt.year
                new_month = dt.month + 1
                
            # Узнаем, сколько максимум дней в следующем месяце
            _, last_day = calendar.monthrange(new_year, new_month)
            
            # Берем текущий день, но не больше, чем дней в новом месяце
            new_day = min(dt.day, last_day)
            
            next_dt = dt.replace(year=new_year, month=new_month, day=new_day)
            
            # --- ПРОВЕРКА НА ВЫХОДНЫЕ ---
            # weekday() возвращает 5 для субботы и 6 для воскресенья
            if next_dt.weekday() == 5:    # Если выпадает на субботу
                next_dt -= timedelta(days=1) # Откатываем на 1 день назад (на пятницу)
            elif next_dt.weekday() == 6:  # Если выпадает на воскресенье
                next_dt -= timedelta(days=2) # Откатываем на 2 дня назад (на пятницу)
                
            return next_dt.strftime("%d.%m.%Y")
        except ValueError:
            return date_str

    @staticmethod
    def generate_history_log(message):
        """Генерирует стандартизированный объект события истории."""
        from tabs.models import HistoryEvent
        from datetime import datetime
        return HistoryEvent(
            timestamp=datetime.now(),
            action=message,
            details=""
        )
    @staticmethod
    def generate_history_html(task) -> str:
        """Генерирует красивый HTML-таймлайн истории задачи."""
        history = getattr(task, "history", [])
        timeline_html = """
        <style>
            .timeline { font-family: 'Segoe UI', sans-serif; padding: 5px; }
            .event { margin-bottom: 12px; border-left: 2px solid #34495e; padding-left: 10px; position: relative; }
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
                marker = "🟢"
                border_color = "#2ecc71"
            elif "работу" in lower_action or "таймер" in lower_action:
                marker = "🔵"
                border_color = "#3498db"
            elif "перенос" in lower_action or "отложен" in lower_action:
                marker = "🟡"
                border_color = "#f1c40f"
            elif "скриншот" in lower_action or "файл" in lower_action:
                marker = "🟠"
                border_color = "#e67e22"
            elif "просроч" in lower_action or "ошибк" in lower_action or "вышло" in lower_action:
                marker = "🔴"
                border_color = "#e74c3c"

            time_part = f'<div class="time">{marker} {ts_str}</div>' if ts_str else f'<div class="time">{marker}</div>'
            timeline_html += f"""
            <div class="event" style="border-left-color: {border_color};">
                {time_part}
                <div class="action">{action_text}</div>
            </div>
            """

        timeline_html += "</div>"
        return timeline_html
    @staticmethod
    def complete_task(task):
        """Останавливает таймер и переводит задачу в статус 'Завершено'."""
        TaskService.stop_timer(task)
        task.status = "Завершено"
        task.history.append(TaskService.generate_history_log("Задача завершена"))

    @staticmethod
    def reschedule_task(task, new_dt):
        """Переносит задачу на новую дату и время, корректно списывая время."""
        from tabs.utils import format_time_spent
        
        TaskService.stop_timer(task)
        
        spent_seconds = getattr(task, 'time_spent', 0)
        spent_str = f" [Затрачено: {format_time_spent(spent_seconds)}]" if spent_seconds > 0 else ""
        if spent_seconds > 0:
            task.time_spent = 0
            
        old_dt_str = task.deadline.strftime("%d.%m.%Y %H:%M")
        
        # Обновляем данные
        task.deadline = new_dt
        task.status = "Ожидание"
        
        new_dt_str = task.deadline.strftime("%d.%m.%Y %H:%M")
        task.history.append(TaskService.generate_history_log(
            f"Перенос вручную{spent_str}: с {old_dt_str} на {new_dt_str}"
        ))
    
    

class CloudService:
    def __init__(self, db_file, settings_file):
        self.db_file = db_file
        self.settings_file = settings_file

    def upload_to_supabase(self, url, api_key):
        """Выгружает данные в Supabase Storage."""
        url = url.strip().rstrip('/')
        if not url or not api_key:
            raise ValueError("Заполните URL проекта и API ключ Supabase.")
            
        bucket_name = "tasktimer-backups"
        headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/octet-stream",
            "x-upsert": "true"  # Перезаписывать файл, если он уже существует
        }
        
        def upload_file(file_path, file_name):
            if not os.path.exists(file_path): return
            endpoint = f"{url}/storage/v1/object/{bucket_name}/{file_name}"
            with open(file_path, 'rb') as f:
                data = f.read()
            req = urllib.request.Request(endpoint, data=data, headers=headers, method='POST')
            urllib.request.urlopen(req, timeout=15)

        try:
            upload_file(self.db_file, "tasks.db")
            if os.path.exists(self.settings_file):
                upload_file(self.settings_file, "settings.json")
            return bucket_name
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8')
            raise Exception(f"Ошибка Supabase (HTTP {e.code}): {error_msg}\nУбедитесь, что бакет '{bucket_name}' создан.")
        except Exception as e:
            raise Exception(f"Ошибка сети: {e}")

    def download_from_supabase(self, url, api_key):
        """Скачивает данные из Supabase Storage."""
        url = url.strip().rstrip('/')
        if not url or not api_key:
            raise ValueError("Заполните URL проекта и API ключ Supabase.")
            
        bucket_name = "tasktimer-backups"
        headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}"
        }
        
        def download_file(file_path, file_name):
            endpoint = f"{url}/storage/v1/object/{bucket_name}/{file_name}"
            req = urllib.request.Request(endpoint, headers=headers, method='GET')
            with urllib.request.urlopen(req, timeout=15) as response:
                with open(file_path, 'wb') as f:
                    f.write(response.read())

        try:
            download_file(self.db_file, "tasks.db")
            try:
                download_file(self.settings_file, "settings.json")
            except Exception as e:
                log.warning(f"Файл настроек не найден в облаке: {e}")
        except urllib.error.HTTPError as e:
            raise Exception(f"Бэкап не найден или доступ запрещен (HTTP {e.code}).")
        except Exception as e:
            raise Exception(f"Ошибка сети: {e}")

class UpdateService:
    def __init__(self, app_dir):
        self.app_dir = app_dir

    def perform_update(self, download_url):
        """Скачивает обновление и запускает скрипт замены файлов."""
        current_exe_path = sys.executable 
        new_exe_path = os.path.join(self.app_dir, "TaskTimer_new.exe")
        bat_path = os.path.join(self.app_dir, "updater.bat")
        current_pid = os.getpid()
        exe_name = os.path.basename(current_exe_path)
        
        # 1. Скачиваем новый exe
        urllib.request.urlretrieve(download_url, new_exe_path)
        
        # 2. Формируем bat скрипт
        bat_content = f"""@echo off
chcp 65001
taskkill /f /im "{exe_name}" >nul 2>&1
taskkill /f /pid {current_pid} >nul 2>&1
:wait_loop
tasklist /fi "PID eq {current_pid}" | find "{current_pid}" >nul
if %errorlevel% == 0 ( timeout /t 1 /nobreak >nul & goto wait_loop )
timeout /t 3 /nobreak >nul
move /y "{new_exe_path}" "{current_exe_path}"
if errorlevel 1 ( timeout /t 2 /nobreak >nul & move /y "{new_exe_path}" "{current_exe_path}" )
start "" "{current_exe_path}"
(goto) 2>nul & del "%~f0"
"""
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        
        # 3. Чистим переменные окружения, чтобы скрипт не наследовал системный мусор от PyInstaller
        env = os.environ.copy()
        env.pop('_MEIPASS2', None)
        env.pop('_MEIPASS', None)
        env.pop('PYTHONHOME', None)
        env.pop('PYTHONPATH', None)
        
        # 4. Запускаем скрипт
        subprocess.Popen([bat_path], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE, env=env)