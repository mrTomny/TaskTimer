# --- КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ ---
GITHUB_API_URL = "https://api.github.com/repos/mrTomny/TaskTimer/releases/latest"
GITHUB_ISSUES_URL = "https://github.com/mrTomny/TaskTimer/issues/new"
# -------------------------------


import os
import ctypes
import winsound
import re
import json
import urllib.request
from datetime import datetime, timezone, timedelta

from PyQt6.QtCore import Qt, QRect, QPoint, QThread, pyqtSignal, QTimer, QRectF, QSize, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QFont, QFontMetrics, QPolygonF, QPen, QBrush, QPainterPath
from PyQt6.QtWidgets import QWidget, QApplication, QFileDialog, QVBoxLayout, QLabel, QPushButton
from tabs.models import Task, HistoryEvent
from tabs.components import SnippingWidget
import logging
log = logging.getLogger("TaskTimer")

def calculate_dynamic_time(task, tz_offset):
    """
    Универсальный калькулятор потраченного времени.
    Возвращает кортеж: (секунды_всего, отформатированная_строка)
    """
    if not task:
        return 0, "00:00"

    base_spent = getattr(task, 'time_spent', 0)
    total_spent = base_spent

    # Накидываем время только если задача прямо сейчас в работе
    if getattr(task, "status", "") == "В работе":
        active_since_str = getattr(task, 'active_since', "")
        if active_since_str:
            current_tz = timezone(timedelta(hours=tz_offset))
            try:
                start_dt = datetime.strptime(active_since_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=current_tz)
                elapsed = int((datetime.now(current_tz) - start_dt).total_seconds())
                total_spent = base_spent + elapsed
            except ValueError:
                pass

    # Красивое форматирование ЧЧ:ММ:СС или ММ:СС
    h, r = divmod(total_spent, 3600)
    m, s = divmod(r, 60)
    spent_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    return total_spent, spent_str

def get_app_dir() -> str:
    """Возвращает базовую директорию для хранения логов, БД и настроек программы."""
    app_dir = os.path.join(os.getenv('APPDATA'), 'TaskTimer')
    # Сразу гарантируем, что папка существует, чтобы другие модули не падали с ошибкой
    os.makedirs(app_dir, exist_ok=True) 
    return app_dir



        
        
def extract_spent_time_from_history(history_logs, fallback_date_str=""):
    """
    Парсит историю задачи и возвращает словарь дат и затраченного времени:
    {'ДД.ММ.ГГГГ': '1ч 30м'}
    """
    spent_per_date = {}
    for h in history_logs:
        log_text = h.action if hasattr(h, 'action') else str(h)
        
        if "Затрачено:" in log_text:
            match_time = re.search(r'Затрачено:\s*([\dчм\s]+)', log_text)
            if match_time:
                t_str = match_time.group(1).strip()
                
                # Пытаемся достать дату из объекта
                if hasattr(h, 'timestamp') and isinstance(h.timestamp, datetime):
                    d_str = h.timestamp.strftime("%d.%m.%Y")
                else:
                    # Если даты в объекте нет, ищем её в тексте лога
                    match_date = re.search(r'(\d{2}\.\d{2}\.\d{4})', log_text)
                    d_str = match_date.group(1) if match_date else fallback_date_str
                
                if d_str:
                    spent_per_date[d_str] = t_str
                    
    return spent_per_date


class UpdateCheckerThread(QThread):
    update_found = pyqtSignal(str, str)
    
    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version
        
    def run(self):
            try:
                # --- СТАЛО: Используем константу GITHUB_API_URL вместо жесткой строки ---
                req = urllib.request.Request(GITHUB_API_URL, headers={'User-Agent': 'TaskTimer-App'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    tag_name = data.get("tag_name", "")
                    latest_version = tag_name.lstrip('vV')
                    current_clean = str(self.current_version).lstrip('vV')
                    
                    if latest_version and latest_version != current_clean:
                        download_url = next((asset.get("browser_download_url") for asset in data.get("assets", []) if asset.get("name", "").endswith(".exe")), None)
                        if download_url:
                            self.update_found.emit(tag_name, download_url)
            except Exception: 
                pass


def format_time_spent(total_seconds):
    if not total_seconds:
        return "0м"
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"

class NotificationService:
    """Глобальный сервис для воспроизведения звуков из любого места программы"""
    
    @classmethod
    def play_sound(cls, sound_type, sound_path, loop=False, base_path=""):
        cls.stop_sound()
        play_path = None
        if sound_type == "custom" and os.path.exists(sound_path): 
            play_path = sound_path
        elif sound_type.startswith("preset_"):
            preset_map = {"preset_gong": "gong.wav", "preset_bell": "bell.wav", "preset_retro": "retro.wav"}
            play_path = os.path.join(base_path, "assets", preset_map.get(sound_type, "gong.wav"))

        if play_path and os.path.exists(play_path):
            if play_path.lower().endswith(".mp3"):
                ctypes.windll.winmm.mciSendStringW("close CustomAlert", None, 0, None)
                ctypes.windll.winmm.mciSendStringW(f'open "{play_path}" alias CustomAlert', None, 0, None)
                ctypes.windll.winmm.mciSendStringW(f"play CustomAlert {'repeat' if loop else ''}", None, 0, None)
            else:
                flags = winsound.SND_FILENAME | winsound.SND_ASYNC
                if loop: flags |= winsound.SND_LOOP
                winsound.PlaySound(play_path, flags)
        else:
            flags = winsound.SND_ALIAS | winsound.SND_ASYNC
            if loop: flags |= winsound.SND_LOOP
            winsound.PlaySound("SystemAsterisk", flags)

    @classmethod
    def stop_sound(cls):
        ctypes.windll.winmm.mciSendStringW("stop CustomAlert", None, 0, None)
        ctypes.windll.winmm.mciSendStringW("close CustomAlert", None, 0, None)
        try: 
            winsound.PlaySound(None, winsound.SND_PURGE)
        except: 
            pass

class ScreenshotService:
    """Глобальный сервис для работы со скриншотами"""
    _snipper = None
    
    @classmethod
    def take_screenshot(cls, client_name, screenshots_dir, callback_fn):
        # SnippingWidget должен быть доступен в этой области видимости
        cls._snipper = SnippingWidget(client_name, screenshots_dir, callback_fn)
        cls._snipper.show()

def calculate_countdown_status(deadline_dt, current_time):
    """Универсальная функция расчета оставшегося времени для любых карточек"""
    time_diff = deadline_dt - current_time
    total_sec = int(time_diff.total_seconds())
    
    if total_sec < 0:
        return "Время вышло!"
        
    days, rem = divmod(total_sec, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    
    if days > 0:
        return f"⏳ {days}д {hours:02d}:{mins:02d}:{secs:02d}"
    else:
        return f"⏳ {hours:02d}:{mins:02d}:{secs:02d}"