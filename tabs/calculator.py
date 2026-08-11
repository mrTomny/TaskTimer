from tabs.logger import log
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QTextBrowser, QPushButton, QLineEdit, QGridLayout, QWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from tabs.themes import get_theme_palette

class CalculatorWindow(QDialog):
    # Добавили параметр is_modern
    def __init__(self, parent=None, theme_palette=None, is_modern=False):
        super().__init__(parent)
        self.is_modern = is_modern
        self.theme_palette = theme_palette or get_theme_palette("dark_fantasy")
        
        self.setWindowTitle("Калькулятор")
        self.setFixedSize(320, 420)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        
        self.setup_ui()
        self.apply_theme(self.theme_palette)

    def setup_ui(self):
        main_calc_layout = QVBoxLayout(self)
        main_calc_layout.setContentsMargins(12, 12, 12, 12)
        main_calc_layout.setSpacing(10)
        
        self.calc_display = QLineEdit()
        self.calc_display.setReadOnly(False)
        self.calc_display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.calc_display.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.calc_display.setMinimumHeight(50)
        self.calc_display.returnPressed.connect(self.calculate_from_keyboard)
        main_calc_layout.addWidget(self.calc_display)
        
        grid = QGridLayout()
        grid.setSpacing(6)
        buttons = [
            '7', '8', '9', '/',
            '4', '5', '6', '*',
            '1', '2', '3', '-',
            'C', '0', '=', '+'
        ]
        
        row, col = 0, 0
        for text in buttons:
            btn = QPushButton(text)
            btn.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            btn.setFixedSize(65, 45)
            btn.clicked.connect(lambda checked, t=text: self.on_calc_button(t))
            grid.addWidget(btn, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
                
        main_calc_layout.addLayout(grid)
        
        self.calc_history = QTextBrowser()
        self.calc_history.setFont(QFont("Segoe UI", 10))
        self.calc_history.setMaximumHeight(80)
        self.calc_history.setPlaceholderText("История...")
        main_calc_layout.addWidget(self.calc_history)

    def apply_theme(self, palette):
        self.theme_palette = palette
        bg = palette.get('menu_bg', '#1a1a1a')
        comp_bg = palette.get('cal_comp_bg', '#2a2a2a')
        fg = palette.get('menu_fg', '#ffffff')
        accent = palette.get('in_progress', '#3498db')
        border = palette.get('version', '#555555')
        
        # === ДИНАМИЧЕСКАЯ ФОРМА ===
        if getattr(self, 'is_modern', False):
            radius_main = "12px"
            radius_btn = "22px"  # Овальные кнопки (ровно половина от высоты 45px)
            radius_input = "15px"
        else:
            radius_main = "4px"
            radius_btn = "4px"   # Прямоугольные строгие кнопки
            radius_input = "4px"
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {fg};
            }}
            QLineEdit {{
                background-color: {comp_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {radius_input};
                padding: 5px;
            }}
            QPushButton {{
                background-color: {comp_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {radius_btn};
            }}
            QPushButton:hover {{
                background-color: {accent};
                color: #ffffff;
                border-color: {accent};
            }}
            QTextBrowser {{
                background-color: {comp_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {radius_main};
            }}
        """)

    def calculate_from_keyboard(self):
        expression = self.calc_display.text()
        try:
            if all(c in "0123456789+-*/. ()" for c in expression):
                result = str(eval(expression))
                if result.endswith('.0'): result = result[:-2]
                self.calc_history.append(f"{expression} = <b>{result}</b>")
                self.calc_display.setText(result)
            else:
                self.calc_display.setText("Ошибка")
        except Exception:
            self.calc_display.setText("Ошибка")
            
    def on_calc_button(self, text):
        if text == 'C':
            self.calc_display.clear()
        elif text == '=':
            self.calculate_from_keyboard() 
        else:
            if self.calc_display.text() == "Ошибка":
                self.calc_display.clear()
            self.calc_display.setText(self.calc_display.text() + text)