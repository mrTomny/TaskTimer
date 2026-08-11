import os
from tabs.logger import log
from tabs.models import Task
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import Qt

def get_theme_palette(theme_name):
    palettes = {
        "dark_fantasy": {
            "clock": "#d4d4d4", "version": "#555555", "history_bg": "#121212", "history_fg": "#b3b3b3", "in_progress": "#8b0000",
            "expired": "#ff4c4c", "completed": "#404040", "cal_active_bg": "#2a0808", "cal_active_fg": "#e0e0e0", "cal_comp_bg": "#1a1a1a",
            "cal_comp_fg": "#555555", "menu_bg": "#1a1a1a", "menu_fg": "#c0c0c0", "menu_sel": "#331414"
        },
        "1c_gray": {
            "clock": "#111111", "version": "#666666", "history_bg": "#ffffff", "history_fg": "#000000", "in_progress": "#27ae60",
            "expired": "#c0392b", "completed": "#7f8c8d", "cal_active_bg": "#d0d4dc", "cal_active_fg": "#000000",
            "cal_comp_bg": "#e4e6eb", "cal_comp_fg": "#555555", "menu_bg": "#d8dcde", "menu_fg": "#1a1a1a", "menu_sel": "#b5c2cb"
        },
        "1c_classic": {
            "clock": "#000000", "version": "#999999", "history_bg": "#ffffff", "history_fg": "#000000", 
            "in_progress": "#f39c12", "expired": "#c0392b", "completed": "#e6d5a1", 
            "cal_active_bg": "#fdf5ce", "cal_active_fg": "#000000", "cal_comp_bg": "#fcf8e3", 
            "cal_comp_fg": "#999999", "menu_bg": "#ffffff", "menu_fg": "#000000", "menu_sel": "#fdf5ce"
        },
        "1c_dark": {
            "clock": "#a9b7c6", "version": "#666666", "history_bg": "#1e1e1e", "history_fg": "#a9b7c6", 
            "in_progress": "#3498db", "expired": "#e74c3c", "completed": "#4c5052", 
            "cal_active_bg": "#555555", "cal_active_fg": "#a9b7c6", "cal_comp_bg": "#3c3f41", 
            "cal_comp_fg": "#666666", "menu_bg": "#2b2b2b", "menu_fg": "#a9b7c6", "menu_sel": "#4c5052"
        },
        "nature_forest": {
            "clock": "#d8e3d3", "version": "#5c7a65", "history_bg": "#151f18", "history_fg": "#eaf2e8", 
            "in_progress": "#2ecc71", "expired": "#e74c3c", "completed": "#395743", 
            "cal_active_bg": "#2c4535", "cal_active_fg": "#d8e3d3", "cal_comp_bg": "#283b2e", 
            "cal_comp_fg": "#5c7a65", "menu_bg": "#1f2e24", "menu_fg": "#d8e3d3", "menu_sel": "#283b2e"
        },
        "cyberpunk": {
            "clock": "#00ffcc", "version": "#e94560", "history_bg": "#0b0b14", "history_fg": "#00ffcc", 
            "in_progress": "#00ffcc", "expired": "#ff0055", "completed": "#e94560", 
            "cal_active_bg": "#0f3460", "cal_active_fg": "#00ffcc", "cal_comp_bg": "#1a1a2e", 
            "cal_comp_fg": "#e94560", "menu_bg": "#0f0f1c", "menu_fg": "#00ffcc", "menu_sel": "#1a1a2e"
        },
        "sapphire_night": {
            "clock": "#66b3ff",        # Яркий небесно-голубой для часов
            "version": "#4a6b8c",      # Приглушенный синий для второстепенного текста
            "history_bg": "#0a192f",   # Глубокий, насыщенный темно-синий фон (основа)
            "history_fg": "#ccd6f6",   # Приятный светло-голубоватый текст
            "in_progress": "#0055ff",  # Ультра-насыщенный синий для активной задачи и дуги таймера
            "expired": "#ff2a5f",      # Контрастный малиново-красный для просроченных задач
            "completed": "#1d3557",    # Спокойный морской синий для завершенных задач
            "cal_active_bg": "#112240",# Фон активных списков (чуть светлее основного фона)
            "cal_active_fg": "#66b3ff",# Голубой текст для активных элементов
            "cal_comp_bg": "#0f172a",  # Плотный темно-синий для панелей и списков
            "cal_comp_fg": "#8892b0",  # Серо-синий текст для неактивных элементов
            "menu_bg": "#020c1b",      # Самый темный синий для главного окна и меню
            "menu_fg": "#e2e8f0",      # Чистый, слегка холодный белый для главного текста
            "menu_sel": "#1e3a8a"      # Ярко выраженное синее выделение при наведении
        }
    }
    return palettes.get(theme_name, palettes["dark_fantasy"])

def create_checkmark_image(app_dir, color_hex):
    path = os.path.join(app_dir, "check_icon.png")
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    pen = QPen(QColor(color_hex))
    pen.setWidth(2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    
    painter.drawLine(4, 9, 8, 13)
    painter.drawLine(8, 13, 14, 5)
    painter.end()
    
    pixmap.save(path, "PNG")
    return path.replace('\\', '/')

def get_stylesheet(pal, check_icon_path):
    return f"""
    /* 1. Убрали QWidget, чтобы контейнеры (макеты) оставались прозрачными и не перекрывали рамки */
    QMainWindow, QDialog {{ background-color: {pal['menu_bg']}; color: {pal['menu_fg']}; }}
    QLabel, QCheckBox, QDockWidget {{ color: {pal['menu_fg']}; background: transparent; }}
    
    /* 2. Добавили QDateEdit и QTimeEdit к выпадающим спискам */
    QComboBox, QDateEdit, QTimeEdit {{ 
        background-color: {pal['cal_comp_bg']}; 
        border: 1px solid {pal['version']}; 
        border-radius: 6px; 
        padding: 6px 10px; 
        color: {pal['menu_fg']}; 
    }}
    QComboBox:focus, QDateEdit:focus, QTimeEdit:focus {{ 
        border: 2px solid {pal['in_progress']}; 
    }}
    
    /* Текстовые поля */
    QLineEdit, QTextEdit, QTextBrowser {{ 
        background-color: {pal['history_bg']}; 
        border: 1px solid {pal['version']}; 
        color: {pal['history_fg']}; 
        border-radius: 6px; 
        padding: 8px; 
    }}
    QLineEdit:focus, QTextEdit:focus {{ 
        border: 2px solid {pal['in_progress']}; 
    }}
    
    /* --- Вкладки и списки (без изменений) --- */
    QTabWidget::pane {{ border: 1px solid {pal['version']}; background-color: {pal['menu_bg']}; border-radius: 6px; }}
    QTabBar::tab {{ background-color: {pal['cal_comp_bg']}; color: {pal['menu_fg']}; padding: 8px 20px; border: 1px solid {pal['version']}; border-bottom: none; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
    QTabBar::tab:selected {{ background-color: {pal['menu_bg']}; color: {pal['in_progress']}; border: 2px solid {pal['in_progress']}; border-bottom: none; }}
    
    QListWidget {{ background-color: {pal['cal_comp_bg']}; border: 1px solid {pal['version']}; border-radius: 6px; padding: 5px; outline: none; color: {pal['menu_fg']}; }}
    QListWidget::item {{ padding: 10px; border: 1px solid transparent; border-bottom: 1px solid {pal['menu_bg']}; border-radius: 4px; margin-bottom: 2px; }}
    QListWidget::item:selected {{ background-color: {pal['menu_sel']}; border: 1px solid {pal['in_progress']}; }}
    
    /* --- Кнопки --- */
    QPushButton {{ background-color: {pal['cal_comp_bg']}; border: 1px solid {pal['version']}; color: {pal['menu_fg']}; border-radius: 6px; padding: 8px; font-weight: bold; }}
    QPushButton:hover {{ background-color: {pal['menu_sel']}; border-color: {pal['in_progress']}; }}
    QPushButton:disabled {{ background-color: {pal['menu_bg']}; color: {pal['version']}; border-color: {pal['cal_comp_bg']}; }}
    
    QPushButton#primaryBtn {{ background-color: #3498db; color: #ffffff; border: none; font-size: 14px; }}
    QPushButton#primaryBtn:hover {{ background-color: #2980b9; }}
    QPushButton#primaryBtn:disabled {{ background-color: {pal['menu_bg']}; color: {pal['version']}; border: 1px solid {pal['cal_comp_bg']}; }}
    
    QListView::indicator, QCheckBox::indicator {{ width: 18px; height: 18px; border: 2px solid {pal['version']}; border-radius: 4px; background-color: transparent; }}
    QListView::indicator:hover, QCheckBox::indicator:hover {{ border: 2px solid {pal['menu_fg']}; }}
    QListView::indicator:checked, QCheckBox::indicator:checked {{ background-color: transparent; border: 2px solid {pal['menu_fg']}; image: url("{check_icon_path}"); }}

    /* ==================================================== */
    /* ИНТЕГРАЦИЯ СОВРЕМЕННОГО ИНТЕРФЕЙСА (MODERN WORKSPACE)*/
    /* ==================================================== */
    
    /* 3. Стили TaskCard полностью удалены отсюда. Ими управляет метод apply_theme_styles() в modern_ui.py */
    
    QFrame#modernDetailsPanel {{
        background-color: {pal['cal_comp_bg']};
        border-radius: 12px;
        border: 1px solid {pal['version']};
    }}
    
    QPushButton[modernMenuBtn="true"] {{
        text-align: left; 
        padding-left: 15px; 
        border: none; 
        border-radius: 8px;
        background: transparent;
        color: {pal['menu_fg']};
    }}
    QPushButton[modernMenuBtn="true"]:hover {{
        background-color: {pal['menu_sel']};
        color: {pal['in_progress']};
    }}
    """

def get_tag_colors():
    """Возвращает централизованный словарь цветов для тегов задач."""
    return {
        "Без цвета": "",
        "🔴 Красный": "#e74c3c",
        "🟠 Оранжевый": "#e67e22",
        "🟡 Желтый": "#f1c40f",
        "🟢 Зеленый": "#2ecc71",
        "🔵 Синий": "#3498db",
        "🟣 Фиолетовый": "#9b59b6",
        "⚫ Черный": "#34495e"
    }