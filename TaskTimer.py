import traceback
import sys
import json
import os
import shutil
import calendar
import winsound
import ctypes
import re
import csv
import urllib.request
import subprocess
import uuid
import webbrowser
import sqlite3
import base64
from datetime import datetime, timezone, timedelta

from tabs.dialogs import DateRangeDialog, CustomToast, RescheduleDialog, BugReportDialog
from tabs.themes import get_theme_palette, create_checkmark_image, get_stylesheet, get_tag_colors
from tabs.database import DatabaseManager
from tabs.calculator import CalculatorWindow
# Чистые утилиты и сервисы
from tabs.utils import (UpdateCheckerThread, format_time_spent, calculate_dynamic_time,
                        NotificationService, ScreenshotService, calculate_countdown_status, extract_spent_time_from_history, get_app_dir)

# Графические компоненты
from tabs.components import SnippingWidget, CircularMiniPlayer, HourglassMiniPlayer, SquareMiniPlayer
from tabs.logger import log
from tabs.services import CloudService, UpdateService, SettingsService, TaskService
from tabs.models import Task, HistoryEvent
from tabs.repository import TaskRepository

# Рабочие пространства (Интерфейсы)
import tabs.interface_ui
import tabs.modern_ui
from tabs.events import events, REGISTERED_WORKSPACES
from tabs.controller import AppController

from PyQt6.QtWidgets import (QApplication, QMainWindow, QDialog, QMessageBox, 
                             QFileDialog, QCheckBox, QSystemTrayIcon, QStackedWidget, QMenu)
from PyQt6.QtCore import Qt, QTimer, QRect, QByteArray, QUrl
from PyQt6.QtGui import (QColor, QPainter, QPixmap, QIcon, QShortcut, QKeySequence, 
                         QPdfWriter, QPageSize, QTextDocument, QCursor, QDesktopServices)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
   
# =========================================================================
# ГЛАВНОЕ ОКНО ПРОГРАММЫ (Хост-контейнер)
# =========================================================================
class GuildDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_version = "v1.5"
        self.setWindowTitle(f"Таймер задач - {self.current_version}")
        self.resize(1600, 900) 
        self._initial_geometry = self.geometry()
        
        self.is_mini_player = False
        self.is_focus_mode = False
        self.normal_geometry = QRect()
        self.normal_state = QByteArray()
        self.saved_mini_geometry = ""
        
        icon_path = get_resource_path("TaskTimer.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.app_dir = get_app_dir()
        
        # --- СТАЛО: Проверка на тестовый режим ---
        if "--test" in sys.argv:
            self.db_file = os.path.join(self.app_dir, "tasks_test.db")
            self.setWindowTitle(f"Таймер задач - {self.current_version} [ТЕСТОВЫЙ РЕЖИМ]")
        else:
            self.db_file = os.path.join(self.app_dir, "tasks.db")
            
        self.data_file = os.path.join(self.app_dir, "tasks.json")
        self.settings_file = os.path.join(self.app_dir, "settings.json")
        
        self.tz_offset, self.sound_type, self.sound_path, self.screenshots_dir = 3, "system", "", ""
        self.show_exit_warning, self.current_theme, self.is_testing_sound, self.force_quit = True, "dark_fantasy", False, False
        self.pending_update_url = None
        self.saved_geometry = ""
        self.saved_state = ""
        self._is_loading_settings = False
        
        # --- СИСТЕМНЫЕ СЕРВИСЫ ---
        self.db = DatabaseManager(self.db_file, self.data_file)
        self.task_repo = TaskRepository(self.db)
        self.cloud_service = CloudService(self.db_file, self.settings_file)
        self.update_service = UpdateService(self.app_dir)
        self.settings_service = SettingsService(self.settings_file)        
        
        self.mini_player_opacity = 0.5
        
        self.setup_tray_icon()
        self.setup_hotkeys()
        
        self.controller = AppController(self.task_repo, self.db, lambda: self.tz_offset)
        
        # --- ДИНАМИЧЕСКАЯ СБОРКА ИНТЕРФЕЙСОВ ИЗ КОРОБКИ ---
        self.main_stack = QStackedWidget(self)
        self.setCentralWidget(self.main_stack)

        self.workspaces = []
        for ws_info in REGISTERED_WORKSPACES:
            # Автоматически создаем каждый зарегистрированный экран
            ws_instance = ws_info["class"](self.task_repo, self.controller, self)
            self.main_stack.addWidget(ws_instance)
            self.workspaces.append(ws_instance)
        
        self.load_settings() 
        self.apply_theme()
        
        # Слушаем команду контроллера на переключение
        events.ui_mode_changed.connect(self.on_ui_mode_changed)
        
        # Умное восстановление активного окна без жестких ограничений (0, 1, 2...)
        saved_index = getattr(self, 'current_ui_index', 0)
        # Защита от сбоев: если сохраненный индекс больше, чем у нас есть экранов
        safe_index = max(0, min(saved_index, self.main_stack.count() - 1))
        
        self.main_stack.setCurrentIndex(safe_index)
            
        # Сигналы диалогов и всплывающих окон
        events.action_reschedule_task.connect(self.reschedule_task)
        events.action_screenshot.connect(self.trigger_screenshot)
        events.action_edit_task.connect(self.edit_task)
        
        # === ИСПРАВЛЕНИЕ БАГА 3: Подключаем проверку просрочки ===
        events.timer_tick.connect(self.check_expired_tasks)
        
        self.update_thread = UpdateCheckerThread(self.current_version)
        self.update_thread.update_found.connect(self.show_update_indicator)
        self.update_thread.start()
        
        self.auto_update_timer = QTimer(self)
        self.auto_update_timer.setInterval(2 * 60 * 60 * 1000)
        self.auto_update_timer.timeout.connect(self.background_check_for_updates)
        self.auto_update_timer.start()

        if self.saved_geometry:
            self.restoreGeometry(QByteArray.fromBase64(self.saved_geometry.encode('utf-8')))
        if self.saved_state:
            self.restoreState(QByteArray.fromBase64(self.saved_state.encode('utf-8')))
            
        # === ИСПРАВЛЕНИЕ: Восстанавливаем размеры интерфейсов ПОСЛЕ того, как главное окно приняло свои размеры ===
        if hasattr(self, 'saved_ui_states'):
            for i in range(self.main_stack.count()):
                ws = self.main_stack.widget(i)
                if hasattr(ws, 'restore_layout_state'):
                    ws.restore_layout_state(self.saved_ui_states.get(f"ui_{i}", {}))

    def prevent_sleep(self, enable=True):
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
        try:
            if enable: ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
            else: ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception as e: log.error(f"Ошибка блокировки сна: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        self.prevent_sleep(True)

    def on_ui_mode_changed(self, mode_index):
        """Переключает видимый контейнер и заставляет экраны обновить свои настройки"""
        self.main_stack.setCurrentIndex(mode_index)
        self.current_ui_index = mode_index
        
        for i in range(self.main_stack.count()):
            ws = self.main_stack.widget(i)
            if hasattr(ws, 'get_settings_panel'):
                panel = ws.get_settings_panel()
                if panel and hasattr(panel, 'combo_ui_mode'):
                    panel.combo_ui_mode.blockSignals(True)
                    panel.combo_ui_mode.setCurrentIndex(mode_index)
                    panel.combo_ui_mode.blockSignals(False)
                    
        self.save_settings()
        
    def get_settings_target(self):
        """Динамически запрашивает панель настроек у активного экрана"""
        active_ws = self.main_stack.currentWidget()
        if hasattr(active_ws, 'get_settings_panel'):
            return active_ws.get_settings_panel()
        return None
        
    def get_current_task(self):
        """Динамически запрашивает выбранную задачу у активного экрана"""
        active_ws = self.main_stack.currentWidget()
        if hasattr(active_ws, 'get_current_task'):
            return active_ws.get_current_task()
        return None

    def on_opacity_changed(self, value):
        self.mini_player_opacity = value / 100.0
        
        # Обновляем прозрачность на лету для ВСЕХ существующих плееров
        if hasattr(self, 'circular_player') and self.circular_player:
            self.circular_player.setWindowOpacity(self.mini_player_opacity)
            
        if hasattr(self, 'hourglass_player') and self.hourglass_player:
            self.hourglass_player.setWindowOpacity(self.mini_player_opacity)
            
        if hasattr(self, 'square_player') and self.square_player:
            self.square_player.setWindowOpacity(self.mini_player_opacity)
            
        self.save_settings()
    
    def check_expired_tasks(self):
        """Проверяет просрочку задач, включает звук и всегда показывает удобное окошко в программе"""
        current_tz = timezone(timedelta(hours=self.tz_offset))
        current_time = datetime.now(current_tz)
        data_changed_in_bg = False
        
        for task in self.task_repo.get_all():
            if getattr(task, "status", "Ожидание") == "Ожидание" and hasattr(task, "deadline"):
                try:
                    task_dt = task.deadline.replace(tzinfo=current_tz)
                    if current_time >= task_dt:
                        task.status = "Время вышло"
                        task.history.append(TaskService.generate_history_log("Сработал таймер"))
                        self.task_repo.update(task)
                        data_changed_in_bg = True
                        
                        NotificationService.play_sound(self.sound_type, self.sound_path, loop=True, base_path=get_resource_path(""))
                        
                        # Вызываем окошко прямо в программе, передавая parent=self для привязки темы
                        self.show_timer_expired_toast(task)
                    else:
                        total_sec = int((task_dt - current_time).total_seconds())
                        if 295 <= total_sec <= 300 and not getattr(task, "_notified_5min", False):
                            task._notified_5min = True
                            client_name = getattr(task, "client", "Без клиента")
                            task_name = getattr(task, "task", "Без названия")
                            if hasattr(self, 'tray_icon') and self.tray_icon:
                                self.tray_icon.showMessage("Скоро начало задачи!", f"Через 5 минут: {client_name} — {task_name}", QSystemTrayIcon.MessageIcon.Information, 5000)
                except ValueError:
                    pass
                    
        if data_changed_in_bg:
            events.data_changed.emit()

    def background_check_for_updates(self):
        if hasattr(self, 'bg_update_thread') and self.bg_update_thread.isRunning(): return
        if self.pending_update_url: return # Если уже нашли обновление - не ищем снова
            
        self.bg_update_thread = UpdateCheckerThread(self.current_version)
        self.bg_update_thread.update_found.connect(self.on_bg_update_found)
        self.bg_update_thread.start()

    def on_bg_update_found(self, latest_version, download_url):
        self.pending_update_url = download_url
        self.notify_workspaces_update(latest_version)
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.showMessage("Доступно обновление", f"Версия {latest_version} ждет установки в панели программы.", QSystemTrayIcon.MessageIcon.Information, 4000)

    # --- МИНИ-ПЛЕЕРЫ ---
    def toggle_mini_player(self):
        style = getattr(self, 'mini_player_style', 'circular')
        
        if style == "hourglass":
            if not hasattr(self, 'hourglass_player'):
                self.hourglass_player = HourglassMiniPlayer(self, tz_offset=self.tz_offset)
                self.hourglass_player.return_requested.connect(self.toggle_mini_player)
                self.hourglass_player.add_task_requested.connect(self.add_task)
                self.hourglass_player.apply_theme(self.get_theme_palette())
                self.hourglass_player.setWindowOpacity(self.mini_player_opacity)
                self.controller.task_started.connect(self.hourglass_player.on_task_started)
                self.controller.task_stopped.connect(self.hourglass_player.on_task_stopped)

            if not self.is_mini_player:
                self.is_mini_player = True
                self.normal_geometry = self.geometry()
                self.hide()
                self.update_mini_player_task()
                self.hourglass_player.show()
            else:
                self.is_mini_player = False
                self.hourglass_player.hide()
                self.setGeometry(self.normal_geometry)
                self.show()

        elif style == "circular":
            if not hasattr(self, 'circular_player'):
                self.circular_player = CircularMiniPlayer(self, tz_offset=self.tz_offset)
                self.circular_player.return_requested.connect(self.toggle_mini_player)
                self.circular_player.add_task_requested.connect(self.add_task)
                self.circular_player.apply_theme(self.get_theme_palette())
                self.circular_player.setWindowOpacity(self.mini_player_opacity)
                self.controller.task_started.connect(self.circular_player.on_task_started)
                self.controller.task_stopped.connect(self.circular_player.on_task_stopped)

            if not self.is_mini_player:
                self.is_mini_player = True
                self.normal_geometry = self.geometry()
                self.hide()
                self.update_mini_player_task()
                self.circular_player.show()
            else:
                self.is_mini_player = False
                self.circular_player.hide()
                self.setGeometry(self.normal_geometry)
                self.show()

        else:
            if not hasattr(self, 'square_player'):
                self.square_player = SquareMiniPlayer(self, tz_offset=self.tz_offset)
                self.square_player.return_requested.connect(self.toggle_mini_player)
                self.square_player.add_task_requested.connect(self.add_task)
                self.square_player.apply_theme(self.get_theme_palette())
                self.square_player.setWindowOpacity(self.mini_player_opacity)
                self.controller.task_started.connect(self.square_player.on_task_started)
                self.controller.task_stopped.connect(self.square_player.on_task_stopped)
                
            if not self.is_mini_player:
                self.is_mini_player = True
                self.normal_geometry = self.geometry()
                self.hide()
                self.update_mini_player_task()
                self.square_player.show()
            else:
                self.is_mini_player = False
                self.square_player.hide()
                self.setGeometry(self.normal_geometry)
                self.show()
            
    def update_mini_player_task(self):
        if not self.is_mini_player: return
        active_tasks = [t for t in self.task_repo.get_all() if getattr(t, "status", "") in ("Ожидание", "В работе")]
        if not active_tasks:
            text_to_show = "Нет активных задач"
        else:
            active_tasks.sort(key=lambda x: getattr(x, 'deadline', datetime.max))
            closest_task = active_tasks[0]
            client = getattr(closest_task, 'client', 'Без клиента')
            task_text = getattr(closest_task, 'task', '')
            time_str = closest_task.deadline.strftime("%H:%M") if hasattr(closest_task, 'deadline') else ""
            text_to_show = f"⏳ {time_str} | {client}\n{task_text}"
            
        style = getattr(self, 'mini_player_style', 'circular')
        player_to_update = None
        if style == "circular" and hasattr(self, 'circular_player'): player_to_update = self.circular_player
        elif style == "hourglass" and hasattr(self, 'hourglass_player'): player_to_update = self.hourglass_player
        elif style == "square" and hasattr(self, 'square_player'): player_to_update = self.square_player 
            
        if player_to_update:
            player_to_update.set_task_text(text_to_show)
            if active_tasks:
                closest_task = active_tasks[0]
                current_tz = timezone(timedelta(hours=self.tz_offset))
                try:
                    deadline_dt = closest_task.deadline.replace(tzinfo=current_tz)
                    player_to_update.closest_task_dt = deadline_dt
                    active_since_str = getattr(closest_task, 'active_since', "")
                    if active_since_str:
                        start_dt = datetime.strptime(active_since_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=current_tz)
                        player_to_update.task_created_dt = start_dt
                    else:
                        task_key = getattr(closest_task, 'id', None)
                        if not hasattr(self, '_task_creation_times'): self._task_creation_times = {}
                        if task_key not in self._task_creation_times: self._task_creation_times[task_key] = datetime.now(current_tz)
                        player_to_update.task_created_dt = self._task_creation_times[task_key]
                except ValueError as e:
                    log.error(f"Ошибка парсинга дат для мини-плеера: {e}")

    # --- ОБНОВЛЕНИЯ И ОБЛАКО ---
    def show_update_indicator(self, latest_version, download_url):
        self.pending_update_url = download_url
        self.notify_workspaces_update(latest_version)

    def trigger_pending_update(self):
        if self.pending_update_url:
            reply = QMessageBox.question(self, 'Обновление!', 'Установить её прямо сейчас?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes: self.perform_update(self.pending_update_url)

    def manual_check_for_updates(self):
        target = self.get_settings_target()
        if hasattr(target, 'btn_check_update'):
            target.btn_check_update.setText("Идет поиск...")
            target.btn_check_update.setEnabled(False)
        self.manual_thread = UpdateCheckerThread(self.current_version)
        self.manual_thread.update_found.connect(self.on_manual_update_found)
        self.manual_thread.finished.connect(self.on_manual_check_finished)
        self.manual_thread.start()

    def on_manual_update_found(self, latest_version, download_url):
        self.pending_update_url = download_url
        self.notify_workspaces_update(latest_version)
        reply = QMessageBox.question(self, 'Обновление', f'Доступна новая версия: {latest_version}.\nУстановить её прямо сейчас?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: self.perform_update(download_url)

    def on_manual_check_finished(self):
        target = self.get_settings_target()
        if hasattr(target, 'btn_check_update'):
            target.btn_check_update.setText("Проверить обновления вручную")
            target.btn_check_update.setEnabled(True)
        if not self.pending_update_url:
            QMessageBox.information(self, "Проверка обновлений", f"У вас установлена актуальная версия ({self.current_version}). Обновлений нет.")

    def perform_update(self, download_url):
        self.notify_workspaces_update_status("Скачивание...")
        QApplication.processEvents()
        try:
            self.update_service.perform_update(download_url)
            self.force_quit = True
            QApplication.quit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка обновления", f"{e}")
            self.notify_workspaces_update_status("Ошибка")
    
    # --- ЕДИНЫЙ СТАНДАРТ ДЛЯ ИНТЕРФЕЙСОВ ---
    def notify_workspaces_update(self, latest_version):
        """Универсально просит все интерфейсы показать кнопку обновления"""
        for ws in self.workspaces:
            if hasattr(ws, 'btn_update_indicator'):
                ws.btn_update_indicator.setText(f"🎁 Доступна {latest_version}")
                ws.btn_update_indicator.setVisible(True)

    def notify_workspaces_update_status(self, text):
        """Универсально меняет текст на кнопке обновления у всех интерфейсов"""
        for ws in self.workspaces:
            if hasattr(ws, 'btn_update_indicator'):
                ws.btn_update_indicator.setText(text)

    def upload_to_supabase(self, silent=False):
        target = self.get_settings_target()
        url = target.line_supabase_url.text() if hasattr(target, 'line_supabase_url') else ""
        api_key = target.line_supabase_key.text() if hasattr(target, 'line_supabase_key') else ""
        btn_upload = getattr(target, 'btn_cloud_upload', None)
        
        if not silent and btn_upload:
            btn_upload.setText("☁ Выгрузка...")
            btn_upload.setEnabled(False)
            QApplication.processEvents()
        try:
            folder_name = self.cloud_service.upload_to_supabase(url, api_key)
            if not silent: QMessageBox.information(self, "Успех", f"Бэкап успешно сохранен в бакет «{folder_name}»!")
        except Exception as e:
            if not silent: QMessageBox.warning(self, "Ошибка", str(e))
        finally:
            if not silent and btn_upload:
                btn_upload.setText("☁ Выгрузить данные")
                btn_upload.setEnabled(True)

    def download_from_supabase(self):
        target = self.get_settings_target()
        url = target.line_supabase_url.text() if hasattr(target, 'line_supabase_url') else ""
        api_key = target.line_supabase_key.text() if hasattr(target, 'line_supabase_key') else ""
        btn_down = getattr(target, 'btn_cloud_download', None)
        
        if QMessageBox.question(self, "Внимание!", "Загрузка ЗАМЕНИТ все текущие данные. Продолжить?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        if btn_down:
            btn_down.setText("📥 Скачивание...")
            btn_down.setEnabled(False)
            QApplication.processEvents()
        try:
            self.cloud_service.download_from_supabase(url, api_key)
            QMessageBox.information(self, "Готово", "Данные восстановлены из Supabase!")
            self.load_settings()
            self.apply_theme()
            self.task_repo.force_reload()
            
            events.data_changed.emit()
            events.notes_changed.emit()
        except Exception as e: 
            QMessageBox.warning(self, "Ошибка", str(e))
        finally:
            if btn_down:
                btn_down.setText("📥 Скачать из облака")
                btn_down.setEnabled(True)

    # --- ТЕМА И НАСТРОЙКИ ---
    def get_theme_palette(self):
        return get_theme_palette(self.current_theme)
        
    def on_theme_changed(self, theme_name=None):
        if isinstance(theme_name, str): self.current_theme = theme_name
        else:
            target = self.get_settings_target()
            if hasattr(target, 'combo_theme'): self.current_theme = target.combo_theme.currentData()
        self.save_settings()
        self.apply_theme() # Теперь этот метод сам обновит все интерфейсы
    
    def apply_theme(self):
        """Окрашивает глобальные элементы и командует всем экранам перекраситься"""
        pal = self.get_theme_palette()
        check_icon_path = create_checkmark_image(self.app_dir, pal['menu_fg'])
        self.setStyleSheet(get_stylesheet(pal, check_icon_path))
        
        if hasattr(self, 'tray_menu'):
            self.tray_menu.setStyleSheet(f"QMenu {{ background-color: {pal['menu_bg']}; color: {pal['menu_fg']}; border: 1px solid {pal['version']}; font-size: 14px; }} QMenu::item {{ padding: 5px 20px; }} QMenu::item:selected {{ background-color: {pal['menu_sel']}; }}")
        
        if hasattr(self, 'circular_player'): self.circular_player.apply_theme(pal)
        if hasattr(self, 'hourglass_player'): self.hourglass_player.apply_theme(pal)
        if hasattr(self, 'square_player'): self.square_player.apply_theme(pal)

        # Вызываем стандартизированный метод у всех интерфейсов!
        for i in range(self.main_stack.count()):
            ws = self.main_stack.widget(i)
            if hasattr(ws, 'apply_theme'):
                ws.apply_theme(pal)

    def load_settings(self):
        """Загружает настройки из БД и раздает их экранам на отрисовку"""
        self._is_loading_settings = True
        data = self.settings_service.load()
        
        self.current_ui_index = data.get("current_ui_index", 0)
        self.tz_offset = data.get("tz_offset", 3)
        self.sound_type = data.get("sound_type", "system")
        self.sound_path = data.get("sound_path", "")
        self.screenshots_dir = data.get("screenshots_dir", "")
        self.show_exit_warning = data.get("show_exit_warning", True)
        self.current_theme = data.get("current_theme", "dark_fantasy")
        self.saved_geometry = data.get("window_geometry", "")
        self.saved_state = data.get("window_state", "")
        self.saved_mini_geometry = data.get("mini_geometry", "")
        self.mini_player_style = data.get("mini_player_style", "circular")
        self.mini_player_opacity = data.get("mini_player_opacity", 0.5)
        self.dev_mode = data.get("dev_mode", False)
        
        # Получаем сохраненные размеры панелей для каждого интерфейса
        self.saved_ui_states = data.get("ui_states", {})
        
        # Обновляем все интерфейсы через единый стандарт (SOLID)!
        for i in range(self.main_stack.count()):
            ws = self.main_stack.widget(i)
            if hasattr(ws, 'update_settings_ui'):
                ws.update_settings_ui(data)
                
        self._is_loading_settings = False

    def save_settings(self):
        """Собирает настройки со всех интерфейсов и сохраняет в БД"""
        if getattr(self, '_is_loading_settings', False): return
        
        # Запрашиваем внутренние размеры у каждого интерфейса
        ui_states = {}
        for i in range(self.main_stack.count()):
            ws = self.main_stack.widget(i)
            if hasattr(ws, 'get_layout_state'):
                ui_states[f"ui_{i}"] = ws.get_layout_state()
        
        geom = self.saveGeometry().toBase64().data().decode('utf-8')
        state = self.saveState().toBase64().data().decode('utf-8')
        
        settings_dict = {
            "tz_offset": getattr(self, 'tz_offset', 3),
            "sound_type": getattr(self, 'sound_type', 'system'),
            "sound_path": getattr(self, 'sound_path', ''),
            "screenshots_dir": getattr(self, 'screenshots_dir', ''),
            "show_exit_warning": getattr(self, 'show_exit_warning', True),
            "current_theme": getattr(self, 'current_theme', 'dark_fantasy'),
            "window_geometry": geom,
            "window_state": state,
            "ui_states": ui_states,  # <--- Теперь мы сохраняем размеры панелей интерфейсов!
            "mini_geometry": getattr(self, 'saved_mini_geometry', ""),
            "current_ui_index": self.main_stack.currentIndex(),
            "mini_player_style": getattr(self, 'mini_player_style', 'circular'),
            "mini_player_opacity": getattr(self, 'mini_player_opacity', 0.5),
            "dev_mode": getattr(self, 'dev_mode', False)
        }
        
        # Безопасное сохранение настроек облака (Supabase)
        target = self.get_settings_target()
        if target:
            if hasattr(target, 'line_supabase_url'): settings_dict["supabase_url"] = target.line_supabase_url.text()
            if hasattr(target, 'line_supabase_key'): settings_dict["supabase_key"] = target.line_supabase_key.text()
            if hasattr(target, 'combo_cloud'): settings_dict["cloud_type_idx"] = target.combo_cloud.currentIndex()
            if hasattr(target, 'cb_auto_backup'): settings_dict["auto_backup"] = target.cb_auto_backup.isChecked()
        else:
            old_data = self.settings_service.load()
            for key in ["supabase_url", "supabase_key", "cloud_type_idx", "auto_backup"]:
                settings_dict[key] = old_data.get(key)
                
        self.settings_service.save(settings_dict)

    # --- СИСТЕМНЫЕ ОКНА И ДЕЙСТВИЯ ---
    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = get_resource_path("TaskTimer.ico")
        if os.path.exists(icon_path): self.tray_icon.setIcon(QIcon(icon_path))
        else:
            icon_pixmap = QPixmap(32, 32); icon_pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(icon_pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("#00a8ff")); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(4, 4, 24, 24); painter.end()
            self.tray_icon.setIcon(QIcon(icon_pixmap))
            
        self.tray_icon.setToolTip("Таймер задач")
        self.tray_menu = QMenu(self)
        self.tray_menu.addAction("Развернуть окно").triggered.connect(self.restore_window)
        self.tray_menu.addAction("Выход (Ctrl+Q)").triggered.connect(self.quit_app)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick: self.restore_window()
    def restore_window(self): self.showNormal(); self.activateWindow(); self.raise_()
    def quit_app(self): self.force_quit = True; QApplication.quit()

    def setup_hotkeys(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.add_task)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.trigger_screenshot)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.quit_app)
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self.toggle_mini_player)
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self.open_calculator)
    
    def open_calculator(self):
        """Открывает или выводит на передний план плавающий калькулятор"""
        active_ws = self.main_stack.currentWidget()
        is_mod = getattr(active_ws, 'is_modern_style', False)
        
        if not hasattr(self, 'calc_window') or not self.calc_window.isVisible():
            pal = self.get_theme_palette()
            self.calc_window = CalculatorWindow(parent=self, theme_palette=pal, is_modern=is_mod)
            self.calc_window.show()
        else:
            self.calc_window.is_modern = is_mod
            self.calc_window.apply_theme(self.get_theme_palette())
            self.calc_window.raise_()
            self.calc_window.activateWindow()

    def closeEvent(self, event):
        self.prevent_sleep(False)
        if self.is_mini_player:
            self.saved_mini_geometry = self.saveGeometry().toBase64().data().decode('utf-8')
            self.setGeometry(self.normal_geometry)
            self.restoreState(self.normal_state)
            
        self.save_settings() 
        target = self.get_settings_target()
        if hasattr(target, 'cb_auto_backup') and target.cb_auto_backup.isChecked() and target.combo_cloud.currentIndex() > 0:
            self.upload_to_supabase(silent=True)
            
        if self.force_quit: event.accept(); return
        if self.show_exit_warning and any(getattr(d, "status", "") != "Завершено" for d in self.task_repo.get_all()):
            msg = QMessageBox(self); msg.setWindowTitle("Выход"); msg.setText("Свернуть программу в трей или закрыть полностью?")
            btn_tray = msg.addButton("В трей", QMessageBox.ButtonRole.ActionRole); btn_quit = msg.addButton("Закрыть полностью", QMessageBox.ButtonRole.DestructiveRole); msg.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
            cb = QCheckBox("Больше не показывать"); msg.setCheckBox(cb); msg.exec()
            if cb.isChecked(): self.show_exit_warning = False; target.cb_exit_warning.setChecked(False); self.save_settings()
            if msg.clickedButton() == btn_quit: self.force_quit = True; QApplication.quit(); event.accept()
            elif msg.clickedButton() == btn_tray: self.hide(); self.tray_icon.showMessage("Таймер", "Фоновый режим", QSystemTrayIcon.MessageIcon.Information, 2000); event.ignore()
            else: event.ignore()
            return
        self.hide(); self.tray_icon.showMessage("Таймер", "Фоновый режим", QSystemTrayIcon.MessageIcon.Information, 2000); event.ignore()

    def mousePressEvent(self, event):
        if self.is_mini_player and event.button() == Qt.MouseButton.LeftButton:
            self.toggle_mini_player()
        super().mousePressEvent(event)

    def on_warning_cb_changed(self, state): self.show_exit_warning = (state == 2); self.save_settings()

    def toggle_test_sound(self):
        target = self.get_settings_target()
        btn = getattr(target, 'btn_test_sound', None)
        if self.is_testing_sound: 
            NotificationService.stop_sound(); self.is_testing_sound = False
            if btn: btn.setText("Тест звука")
        else: 
            NotificationService.play_sound(self.sound_type, self.sound_path, loop=True, base_path=get_resource_path(""))
            self.is_testing_sound = True
            if btn: btn.setText("⏹ Остановить тест")

    def browse_sound_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выберите аудиофайл", "", "Аудио (*.wav *.mp3)")
        if file_name: 
            target = self.get_settings_target()
            if hasattr(target, 'line_sound_path'): target.line_sound_path.setText(file_name)
            self.sound_path = file_name
            self.save_settings()
    
    def on_sound_type_changed(self, index=None):
        target = self.get_settings_target()
        if hasattr(target, 'combo_sound'):
            is_custom = (target.combo_sound.currentData() == "custom")
            if hasattr(target, 'line_sound_path'): target.line_sound_path.setEnabled(is_custom)
            if hasattr(target, 'btn_browse_sound'): target.btn_browse_sound.setEnabled(is_custom)
        self.save_settings()

    def browse_screenshot_dir(self):
        dir_name = QFileDialog.getExistingDirectory(self, "Выберите папку для скриншотов")
        if dir_name: 
            target = self.get_settings_target()
            if hasattr(target, 'line_screenshot_dir'): target.line_screenshot_dir.setText(dir_name)
            self.screenshots_dir = dir_name
            self.save_settings()

    def export_tasks(self):
        dialog = DateRangeDialog(self)
        if not dialog.exec(): return
        start_date_str, end_date_str = dialog.get_dates()
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        file_path, selected_filter = QFileDialog.getSaveFileName(self, "Сохранить отчет", "Отчет_по_задачам", "CSV Files (*.csv);;Excel Files (*.xlsx);;PDF Document (*.pdf)")
        if not file_path: return
        
        filtered_tasks = [t for t in self.task_repo.get_all() if hasattr(t, 'deadline') and start_dt <= t.deadline.date() <= end_dt]
        try:
            if selected_filter.startswith("CSV"):
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f: 
                    writer = csv.writer(f, delimiter=';'); writer.writerow(["Статус", "Клиент", "Задача", "Дедлайн", "История изменений"])
                    for t in filtered_tasks: 
                        deadline_str = t.deadline.strftime("%d.%m.%Y %H:%M") if hasattr(t, 'deadline') else ""
                        t_history = [f"[{h.timestamp.strftime('%d.%m.%Y %H:%M:%S')}] {h.action}" for h in getattr(t, 'history', [])]
                        writer.writerow([getattr(t, 'status', ''), getattr(t, 'client', ''), getattr(t, 'task', ''), deadline_str, " | ".join(t_history)])
            elif selected_filter.startswith("Excel"):
                try: import openpyxl
                except ImportError: QMessageBox.warning(self, "Требуется модуль", "Откройте консоль и введите:\npip install openpyxl"); return
                wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Контракты"; ws.append(["Статус", "Клиент", "Задача", "Дедлайн", "История изменений"])
                for t in filtered_tasks:
                    deadline_str = t.deadline.strftime("%d.%m.%Y %H:%M") if hasattr(t, 'deadline') else ""
                    t_history = [f"[{h.timestamp.strftime('%d.%m.%Y %H:%M:%S')}] {h.action}" for h in getattr(t, 'history', [])]
                    ws.append([getattr(t, 'status', ''), getattr(t, 'client', ''), getattr(t, 'task', ''), deadline_str, " | ".join(t_history)])
                wb.save(file_path)
            elif selected_filter.startswith("PDF"):
                writer = QPdfWriter(file_path); writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4)); writer.setResolution(300); doc = QTextDocument()
                html = "<h1 style='color: #2b2b2b; font-family: sans-serif;'>Отчет по контрактам</h1><table border='1' cellspacing='0' cellpadding='8' width='100%' style='border-collapse: collapse; font-family: sans-serif;'><tr style='background-color: #f2f2f2;'><th>Статус</th><th>Клиент</th><th>Задача</th><th>Дедлайн</th><th>История</th></tr>"
                for t in filtered_tasks:
                    deadline_str = t.deadline.strftime("%d.%m.%Y %H:%M") if hasattr(t, 'deadline') else ""
                    history_html = '<br>'.join([f"[{h.timestamp.strftime('%d.%m.%Y %H:%M:%S')}] {h.action}" for h in getattr(t, 'history', [])])
                    html += f"<tr><td>{getattr(t, 'status', '')}</td><td>{getattr(t, 'client', '')}</td><td>{getattr(t, 'task', '')}</td><td>{deadline_str}</td><td><small>{history_html}</small></td></tr>"
                doc.setHtml(html + "</table>"); doc.print(writer)
            QMessageBox.information(self, "Готово", f"Отчет успешно выгружен!\nЗадач в отчете: {len(filtered_tasks)}")
        except Exception as e: QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить файл:\n{str(e)}")

    def show_timer_expired_toast(self, task):
        client = getattr(task, 'client', 'Без клиента')
        task_name = getattr(task, 'task', 'Без названия')
        
        active_ws = self.main_stack.currentWidget()
        is_mod = getattr(active_ws, 'is_modern_style', False)
        
        dialog = CustomToast(
            f"Клиент: {client}\nЗадача: {task_name}", 
            self.get_theme_palette(), 
            is_modern=is_mod, 
            on_click_callback=self.restore_window, 
            parent=self
        )
        result = dialog.exec()
        if result == 1: events.action_start_work.emit(task)
        elif result == 3: events.action_reschedule_task.emit(task)
        elif result == 4: self.snooze_one_hour(task)
        else: NotificationService.stop_sound()

    def snooze_one_hour(self, task):
        NotificationService.stop_sound()
        current_tz = timezone(timedelta(hours=self.tz_offset))
        new_dt = datetime.now(current_tz) + timedelta(hours=1)
        old_str = task.deadline.strftime("%d.%m.%Y %H:%M")
        task.deadline = new_dt.replace(tzinfo=None)
        task.status = "Ожидание"
        task.history.append(TaskService.generate_history_log(f"Отложено на час: с {old_str} на {task.deadline.strftime('%d.%m.%Y')} {task.deadline.strftime('%H:%M')}"))
        self.task_repo.update(task)
        events.data_changed.emit()

    def add_task(self, *args, is_modern=None):
        active_ws = self.main_stack.currentWidget()
        
        # Полная универсальность: спрашиваем класс диалога у интерфейса
        DialogClass = active_ws.dialog_class
        
        dialog = DialogClass(
            self, 
            title="Новый контракт", 
            tz_offset=self.tz_offset, 
            get_templates_cb=self.controller.get_templates, 
            theme_key=self.current_theme
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            raw_data = dialog.get_task_data()
            if raw_data.get("client", "").strip() or raw_data.get("task", "").strip():
                events.action_add_task.emit(raw_data)

    def trigger_screenshot(self, task_obj=None):
        if not task_obj:
            task_obj = self.get_current_task()
            if not task_obj: return
            
        self._target_screenshot_task = task_obj 
        client_name = getattr(task_obj, "client", "Клиент")
        self.hide()
        QTimer.singleShot(150, lambda: ScreenshotService.take_screenshot(client_name, self.screenshots_dir, self.on_screenshot_captured))
        
    def _start_snipping(self, client_name):
        self.snipper = SnippingWidget(client_name, self.screenshots_dir, self.on_screenshot_captured)
        self.snipper.show()
        
    def on_screenshot_captured(self, file_path):
        self.show()
        if not file_path: return 
        task_obj = getattr(self, '_target_screenshot_task', None) or self.get_current_task()
        if task_obj: events.action_save_screenshot.emit(getattr(task_obj, "id", None), file_path)

    def reschedule_task(self, task_obj=None):
        NotificationService.stop_sound()
        task_obj = task_obj or self.get_current_task()
        if not task_obj: return
        current_date_val = task_obj.deadline.strftime("%d.%m.%Y")
        current_time_val = task_obj.deadline.strftime("%H:%M")
        dialog = RescheduleDialog(self, current_date_val, current_time_val, self.tz_offset)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_dt_dict = dialog.get_new_datetime()
            new_dt = datetime.strptime(f"{new_dt_dict['date']} {new_dt_dict['time']}", "%d.%m.%Y %H:%M")
            events.action_save_reschedule.emit(getattr(task_obj, 'id', None), new_dt)

    def edit_task(self, task_obj=None):
        NotificationService.stop_sound()
        task_obj = task_obj or self.get_current_task()
        if not task_obj: return
        
        active_ws = self.main_stack.currentWidget()
        DialogClass = active_ws.dialog_class
        
        dialog = DialogClass(
            self, 
            title="Редактирование", 
            tz_offset=self.tz_offset, 
            get_templates_cb=self.controller.get_templates, 
            theme_key=self.current_theme
        )
        dialog.set_task_data(task_obj) 
        if dialog.exec() == QDialog.DialogCode.Accepted:
            raw_data = dialog.get_task_data()  
            events.action_save_edit_task.emit(getattr(task_obj, "id", None), raw_data)

    def open_bug_report(self):
        dialog = BugReportDialog(self, app_version=self.current_version)
        dialog.exec()

if __name__ == "__main__":
    try:
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        app = QApplication(sys.argv)
        SERVER_NAME = "TaskTimer_App_v3"
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        
        if socket.waitForConnected(500):
            socket.write(b"WAKE_UP")
            if socket.waitForBytesWritten(500) and socket.waitForReadyRead(500): sys.exit(0)
                
        server = QLocalServer()
        QLocalServer.removeServer(SERVER_NAME)
        server.listen(SERVER_NAME)
        
        app.setQuitOnLastWindowClosed(False)
        app.setStyle("Fusion") 
        window = GuildDashboard()
        
        def on_new_connection():
            client = server.nextPendingConnection()
            if client.waitForReadyRead(500) and client.readAll().data() == b"WAKE_UP": 
                window.restore_window()
                client.write(b"OK")
            client.disconnectFromServer()

        server.newConnection.connect(on_new_connection)
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        with open("crash_log.txt", "w", encoding="utf-8") as f:
            f.write("КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ:\n")
            f.write(traceback.format_exc())