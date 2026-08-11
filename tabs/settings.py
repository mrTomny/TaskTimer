import webbrowser
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFormLayout, QComboBox, QLineEdit, QPushButton, 
                             QCheckBox, QSlider, QFrame, QFileDialog)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QToolTip, QMessageBox

class SecretDevLabel(QLabel):
    """Скрытый триггер режима разработчика"""
    def __init__(self, text, main_win, parent=None):
        super().__init__(text, parent)
        self.main_win = main_win
        self.click_count = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if getattr(self.main_win, 'dev_mode', False):
                return
            
            self.click_count += 1
            if self.click_count >= 7:
                self.main_win.dev_mode = True
                self.main_win.save_settings()
                QMessageBox.information(self, "DEV MODE", "🛠 Режим разработчика активирован!\nВ архиве и календаре разблокировано удаление (ПКМ).")
                self.click_count = 0
            elif self.click_count >= 4:
                QToolTip.showText(event.globalPosition().toPoint(), f"Шагов до режима разработчика: {7 - self.click_count}", self)
        super().mousePressEvent(event)



class SettingsPanelWidget(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_win = main_window
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # 0. Вид интерфейса (АВТОМАТИЧЕСКАЯ СБОРКА ИЗ РЕЕСТРА)
        self.combo_ui_mode = QComboBox(self)
        self.combo_ui_mode.setFont(QFont("Segoe UI", 11))
        
        from tabs.events import REGISTERED_WORKSPACES
        for idx, ws_info in enumerate(REGISTERED_WORKSPACES):
            self.combo_ui_mode.addItem(ws_info["name"], idx)
        
        # Определяем текущий индекс окна
        current_idx = 0
        p = self.parent()
        while p:
            # Ищем, какому классу из реестра принадлежит этот родитель
            for idx, ws_info in enumerate(REGISTERED_WORKSPACES):
                if isinstance(p, ws_info["class"]):
                    current_idx = idx
                    break
            p = p.parent()

        self.combo_ui_mode.blockSignals(True)
        self.combo_ui_mode.setCurrentIndex(current_idx)
        self.combo_ui_mode.blockSignals(False)

        def switch_ui_mode(idx):
            from tabs.events import events
            events.action_switch_ui_mode.emit(idx)

        self.combo_ui_mode.currentIndexChanged.connect(switch_ui_mode)

        # 1. Стиль мини-плеера
        self.combo_mini_style = QComboBox(self)
        self.combo_mini_style.setFont(QFont("Segoe UI", 11))
        self.combo_mini_style.addItem("Круглый (Плавающий)", "circular")
        self.combo_mini_style.addItem("Квадратный (Встроенный)", "square")
        self.combo_mini_style.addItem("Песочные часы", "hourglass")
        
        style_idx = self.combo_mini_style.findData(getattr(self.main_win, 'mini_player_style', 'circular'))
        if style_idx >= 0:
            self.combo_mini_style.setCurrentIndex(style_idx)
            
        # Обновляем переменную перед сохранением
        self.combo_mini_style.currentIndexChanged.connect(lambda: (
            setattr(self.main_win, 'mini_player_style', self.combo_mini_style.currentData()),
            self.main_win.save_settings()
        ))

        # 2. Тема оформления
        self.combo_theme = QComboBox(self)
        self.combo_theme.setFont(QFont("Segoe UI", 11))
        themes = [
            ("Темное Фентези", "dark_fantasy"),
            ("1C Серый Про", "1c_gray"),
            ("1C Классика", "1c_classic"),
            ("1C Темная", "1c_dark"),
            ("Лесная чаща", "nature_forest"),
            ("Киберпанк", "cyberpunk"),
            ("Сапфировая ночь", "sapphire_night")
        ]
        for name, val in themes:
            self.combo_theme.addItem(name, val)
        theme_idx = self.combo_theme.findData(getattr(self.main_win, 'current_theme', 'dark_fantasy'))
        if theme_idx >= 0:
            self.combo_theme.setCurrentIndex(theme_idx)
        self.combo_theme.currentIndexChanged.connect(lambda: self.main_win.on_theme_changed(self.combo_theme.currentData()))

        # 3. Часовой пояс
        self.combo_tz = QComboBox(self)
        self.combo_tz.setFont(QFont("Segoe UI", 11))
        timezone_items = [
            ("(UTC-12:00)", -12), ("(UTC-11:00)", -11), ("(UTC-10:00)", -10), ("(UTC-09:00)", -9),
            ("(UTC-08:00)", -8), ("(UTC-07:00)", -7), ("(UTC-06:00)", -6), ("(UTC-05:00)", -5),
            ("(UTC-04:00)", -4), ("(UTC-03:00)", -3), ("(UTC-02:00)", -2), ("(UTC-01:00)", -1),
            ("(UTC+00:00) Лондон", 0), ("(UTC+01:00) Берлин", 1), ("(UTC+02:00) Киев", 2),
            ("(UTC+03:00) Москва, Санкт-Петербург", 3), ("(UTC+04:00) Самара", 4), 
            ("(UTC+05:00) Екатеринбург", 5), ("(UTC+06:00) Омск", 6), 
            ("(UTC+07:00) Красноярск", 7), ("(UTC+08:00) Иркутск", 8), 
            ("(UTC+09:00) Якутск", 9), ("(UTC+10:00) Владивосток", 10), 
            ("(UTC+11:00) Магадан", 11), ("(UTC+12:00) Камчатка", 12)
        ]
        for label, val in timezone_items:
            self.combo_tz.addItem(label, val)
            if val == getattr(self.main_win, 'tz_offset', 3):
                self.combo_tz.setCurrentIndex(self.combo_tz.count() - 1)
        self.combo_tz.currentIndexChanged.connect(lambda: (
            setattr(self.main_win, 'tz_offset', self.combo_tz.currentData()),
            self.main_win.save_settings()
        ))

        # 4. Тип оповещения
        self.combo_sound = QComboBox(self)
        self.combo_sound.setFont(QFont("Segoe UI", 11))
        self.combo_sound.addItem("Системный звук", "system")
        self.combo_sound.addItem("Встроенный: Гонг", "preset_gong")
        self.combo_sound.addItem("Встроенный: Мягкий звонок", "preset_bell")
        self.combo_sound.addItem("Встроенный: Ретро-сигнал", "preset_retro")
        self.combo_sound.addItem("Свой аудиофайл (.wav, .mp3)", "custom")
        
        sound_idx = self.combo_sound.findData(getattr(self.main_win, 'sound_type', 'system'))
        if sound_idx >= 0:
            self.combo_sound.setCurrentIndex(sound_idx)
        self.combo_sound.currentIndexChanged.connect(self.main_win.on_sound_type_changed)

        # 5. Файл звука
        sound_file_layout = QHBoxLayout()
        self.line_sound_path = QLineEdit(getattr(self.main_win, 'sound_path', ''), self)
        self.line_sound_path.setEnabled(getattr(self.main_win, 'sound_type', 'system') == "custom")
        self.line_sound_path.textChanged.connect(lambda: self.main_win.save_settings())

        self.btn_browse_sound = QPushButton("Обзор...", self)
        self.btn_browse_sound.setEnabled(getattr(self.main_win, 'sound_type', 'system') == "custom")
        self.btn_browse_sound.clicked.connect(self.main_win.browse_sound_file)

        self.btn_test_sound = QPushButton("Тест звука", self)
        self.btn_test_sound.setObjectName("success_btn")
        self.btn_test_sound.clicked.connect(self.main_win.toggle_test_sound)

        sound_file_layout.addWidget(self.line_sound_path)
        sound_file_layout.addWidget(self.btn_browse_sound)
        sound_file_layout.addWidget(self.btn_test_sound)

        # 6. Папка скриншотов
        screenshot_layout = QHBoxLayout()
        self.line_screenshot_dir = QLineEdit(getattr(self.main_win, 'screenshots_dir', ''), self)
        self.line_screenshot_dir.setPlaceholderText("По умолчанию (диалоговое окно сохранения)")
        self.line_screenshot_dir.textChanged.connect(lambda: self.main_win.save_settings())

        self.btn_browse_screenshot = QPushButton("Папка...", self)
        self.btn_browse_screenshot.clicked.connect(self.main_win.browse_screenshot_dir)

        screenshot_layout.addWidget(self.line_screenshot_dir)
        screenshot_layout.addWidget(self.btn_browse_screenshot)

        # 7. Чекбокс выхода
        self.cb_exit_warning = QCheckBox("Показывать предупреждение при закрытии программы", self)
        self.cb_exit_warning.setChecked(getattr(self.main_win, 'show_exit_warning', True))
        self.cb_exit_warning.stateChanged.connect(lambda state: self.main_win.on_warning_cb_changed(state))

        sep1 = QFrame(self)
        sep1.setFrameShape(QFrame.Shape.HLine)

        # 8. Supabase
        self.combo_cloud = QComboBox(self)
        self.combo_cloud.setFont(QFont("Segoe UI", 11))
        self.combo_cloud.addItems(["Отключено", "Supabase Storage"])
        data_settings = self.main_win.settings_service.load()
        saved_cloud_idx = data_settings.get("cloud_type_idx", 0)
        self.combo_cloud.setCurrentIndex(saved_cloud_idx)
        self.combo_cloud.currentIndexChanged.connect(self.on_cloud_combo_changed)

        self.supabase_container = QWidget(self)
        supabase_form = QFormLayout(self.supabase_container)
        supabase_form.setContentsMargins(0, 0, 0, 0)
        supabase_form.setSpacing(8)

        self.line_supabase_url = QLineEdit(data_settings.get("supabase_url", ""), self.supabase_container)
        self.line_supabase_url.setPlaceholderText("https://xxxxxx.supabase.co")
        self.line_supabase_url.textChanged.connect(lambda: self.main_win.save_settings())

        self.line_supabase_key = QLineEdit(data_settings.get("supabase_key", ""), self.supabase_container)
        self.line_supabase_key.setPlaceholderText("service_role key (или anon key)")
        self.line_supabase_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.line_supabase_key.textChanged.connect(lambda: self.main_win.save_settings())

        supabase_form.addRow("Project URL:", self.line_supabase_url)
        supabase_form.addRow("API Key:", self.line_supabase_key)

        self.cb_auto_backup = QCheckBox("Автоматически делать бэкап при выходе", self)
        self.cb_auto_backup.setChecked(data_settings.get("auto_backup", False))
        self.cb_auto_backup.stateChanged.connect(lambda: self.main_win.save_settings())

        self.backup_actions_widget = QWidget(self)
        backup_layout = QHBoxLayout(self.backup_actions_widget)
        backup_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_cloud_upload = QPushButton("☁ Выгрузить данные", self.backup_actions_widget)
        self.btn_cloud_upload.setObjectName("primary_btn")
        self.btn_cloud_upload.clicked.connect(self.main_win.upload_to_supabase)

        self.btn_cloud_download = QPushButton("📥 Скачать из облака", self.backup_actions_widget)
        self.btn_cloud_download.setObjectName("success_btn")
        self.btn_cloud_download.clicked.connect(self.main_win.download_from_supabase)

        backup_layout.addWidget(self.btn_cloud_upload)
        backup_layout.addWidget(self.btn_cloud_download)

        show_supabase = (saved_cloud_idx == 1)
        show_actions = (saved_cloud_idx > 0)
        self.supabase_container.setVisible(show_supabase)
        self.cb_auto_backup.setVisible(show_actions)
        self.backup_actions_widget.setVisible(show_actions)

        sep2 = QFrame(self)
        sep2.setFrameShape(QFrame.Shape.HLine)

        # 9. Кнопки действий
        def make_action_btn(text, obj_name, callback):
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.clicked.connect(callback)
            return btn

        self.btn_export = make_action_btn("Выгрузить отчеты (CSV, Excel, PDF)", "action_btn", self.main_win.export_tasks)
        self.btn_donate = make_action_btn("☕ Поддержать проект", "action_btn", lambda: webbrowser.open("https://yoomoney.ru/fundraise/1J6VD9DG74P.260723"))
        self.btn_check_update = make_action_btn("Проверить обновления вручную", "action_btn", self.main_win.manual_check_for_updates)
        self.btn_bug_report = make_action_btn("🐞 Сообщить об ошибке", "danger_btn", self.main_win.open_bug_report)

        # 10. Слайдер
        opacity_container = QWidget()
        opacity_layout = QVBoxLayout(opacity_container)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(4)
        
        current_opacity = int(getattr(self.main_win, 'mini_player_opacity', 0.5) * 100)
        self.opacity_lbl = QLabel(f"Прозрачность мини-плеера: {current_opacity}%")
        self.opacity_lbl.setObjectName("sub_label")
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(20, 100)
        self.slider.setValue(current_opacity)
        self.slider.valueChanged.connect(lambda val: (
            self.opacity_lbl.setText(f"Прозрачность мини-плеера: {val}%"),
            self.main_win.on_opacity_changed(val)
        ))

        opacity_layout.addWidget(self.opacity_lbl)
        opacity_layout.addWidget(self.slider)

        # Сборка формы
        form_layout.addRow(QLabel("Вид интерфейса:"), self.combo_ui_mode)
        form_layout.addRow(QLabel("Стиль мини-плеера:"), self.combo_mini_style)
        form_layout.addRow(QLabel("Тема оформления:"), self.combo_theme)
        form_layout.addRow(QLabel("Часовой пояс:"), self.combo_tz)
        form_layout.addRow(QLabel("Тип оповещения:"), self.combo_sound)
        form_layout.addRow(QLabel("Файл звука:"), sound_file_layout)
        form_layout.addRow(QLabel("Папка скриншотов:"), screenshot_layout)
        form_layout.addRow("", self.cb_exit_warning)
        form_layout.addRow(sep1)
        form_layout.addRow(QLabel("Облачное хранилище:"), self.combo_cloud)
        form_layout.addRow("", self.supabase_container)
        form_layout.addRow("", self.cb_auto_backup)
        form_layout.addRow(QLabel("Управление базой:"), self.backup_actions_widget)
        form_layout.addRow(sep2)
        form_layout.addRow(QLabel("Экспорт:"), self.btn_export)
        form_layout.addRow(QLabel("Благодарность:"), self.btn_donate)
        form_layout.addRow(QLabel("Обновления:"), self.btn_check_update)
        form_layout.addRow(QLabel("Помощь:"), self.btn_bug_report)
        form_layout.addRow(opacity_container)
        
        version_str = getattr(self.main_win, 'current_version', 'v1.5')
        self.lbl_version = SecretDevLabel(f"Версия программы: {version_str}", self.main_win, self)
        self.lbl_version.setObjectName("sub_label")
        form_layout.addRow("", self.lbl_version)

        main_layout.addLayout(form_layout)

    def on_cloud_combo_changed(self, index):
        show_supabase = (index == 1)
        show_actions = (index > 0)
        self.supabase_container.setVisible(show_supabase)
        self.cb_auto_backup.setVisible(show_actions)
        self.backup_actions_widget.setVisible(show_actions)
        self.main_win.save_settings()
        
    def load_from_data(self, data):
        """Метод инкапсуляции: панель сама настраивает свой UI на основе словаря данных"""
        main_win = self.main_win
        try:
            if hasattr(self, 'combo_mini_style'):
                self.slider.blockSignals(True)
                opacity = getattr(main_win, 'mini_player_opacity', 0.5)
                self.slider.setValue(int(opacity * 100))
                self.slider.blockSignals(False)
                self.opacity_lbl.setText(f"Прозрачность мини-плеера: {int(opacity * 100)}%")
                
                style = getattr(main_win, 'mini_player_style', 'circular')
                style_idx = self.combo_mini_style.findData(style)
                if style_idx >= 0:
                    self.combo_mini_style.blockSignals(True)
                    self.combo_mini_style.setCurrentIndex(style_idx)
                    self.combo_mini_style.blockSignals(False)

            if hasattr(self, 'combo_ui_mode'):
                self.combo_ui_mode.blockSignals(True)
                self.combo_ui_mode.setCurrentIndex(getattr(main_win, 'current_ui_index', 0))
                self.combo_ui_mode.blockSignals(False)
                    
            if hasattr(self, 'combo_tz'): self.combo_tz.blockSignals(True)
            if hasattr(self, 'combo_sound'): self.combo_sound.blockSignals(True)
            if hasattr(self, 'combo_theme'): self.combo_theme.blockSignals(True)
            if hasattr(self, 'combo_cloud'): self.combo_cloud.blockSignals(True)
            if hasattr(self, 'cb_exit_warning'): self.cb_exit_warning.blockSignals(True)

            if hasattr(self, 'combo_tz'):
                tz_idx = self.combo_tz.findData(getattr(main_win, 'tz_offset', 3))
                if tz_idx >= 0: self.combo_tz.setCurrentIndex(tz_idx)
            
            if hasattr(self, 'combo_sound'):
                sound_idx = self.combo_sound.findData(getattr(main_win, 'sound_type', 'system'))
                if sound_idx >= 0: self.combo_sound.setCurrentIndex(sound_idx)
                
            if hasattr(self, 'line_sound_path'):
                self.line_sound_path.blockSignals(True)
                self.line_sound_path.setText(getattr(main_win, 'sound_path', ''))
                self.line_sound_path.blockSignals(False)
                
            if hasattr(self, 'line_screenshot_dir'):
                self.line_screenshot_dir.blockSignals(True)
                self.line_screenshot_dir.setText(getattr(main_win, 'screenshots_dir', ''))
                self.line_screenshot_dir.blockSignals(False)
                
            if hasattr(self, 'cb_exit_warning'): 
                self.cb_exit_warning.setChecked(getattr(main_win, 'show_exit_warning', True))
                
            if hasattr(self, 'combo_theme'):
                theme_idx = self.combo_theme.findData(getattr(main_win, 'current_theme', 'dark_fantasy'))
                if theme_idx >= 0: self.combo_theme.setCurrentIndex(theme_idx)

            if hasattr(self, 'line_supabase_url'):
                self.line_supabase_url.blockSignals(True)
                self.line_supabase_url.setText(data.get("supabase_url", ""))
                self.line_supabase_url.blockSignals(False)
                
                self.line_supabase_key.blockSignals(True)
                self.line_supabase_key.setText(data.get("supabase_key", ""))
                self.line_supabase_key.blockSignals(False)
                
                saved_cloud_idx = data.get("cloud_type_idx", 0)
                self.combo_cloud.setCurrentIndex(saved_cloud_idx)
                self.supabase_container.setVisible(saved_cloud_idx == 1)
                show_actions = saved_cloud_idx > 0
                self.backup_actions_widget.setVisible(show_actions)
                self.cb_auto_backup.setVisible(show_actions)
                self.cb_auto_backup.setChecked(data.get("auto_backup", False))

            if hasattr(self, 'combo_tz'): self.combo_tz.blockSignals(False)
            if hasattr(self, 'combo_sound'): self.combo_sound.blockSignals(False)
            if hasattr(self, 'combo_theme'): self.combo_theme.blockSignals(False)
            if hasattr(self, 'combo_cloud'): self.combo_cloud.blockSignals(False)
            if hasattr(self, 'cb_exit_warning'): self.cb_exit_warning.blockSignals(False)
            
            is_custom = (getattr(main_win, 'sound_type', 'system') == "custom")
            if hasattr(self, 'line_sound_path'): self.line_sound_path.setEnabled(is_custom)
            if hasattr(self, 'btn_browse_sound'): self.btn_browse_sound.setEnabled(is_custom)

        except Exception as e:
            from tabs.logger import log
            log.error(f"Ошибка применения настроек к панели: {e}")