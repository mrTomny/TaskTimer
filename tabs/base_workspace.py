class WorkspaceContract:
    """
    Жесткий стандарт (контракт) для любого экрана TaskTimer.
    Реализован через NotImplementedError, чтобы избежать конфликта метаклассов с PyQt6.
    """
    
    @property
    def dialog_class(self):
        """Класс диалогового окна для создания/редактирования задач"""
        raise NotImplementedError("Экран обязан указать класс диалога (dialog_class)!")

    @property
    def is_modern_style(self):
        """Флаг визуального стиля (True/False) для всплывающих окон и калькулятора"""
        raise NotImplementedError("Экран обязан указать стиль (is_modern_style)!")

    def get_current_task(self):
        """Должен возвращать текущую выделенную задачу или None"""
        raise NotImplementedError("Экран обязан реализовать метод get_current_task()!")

    def get_settings_panel(self):
        """Должен возвращать виджет панели настроек или None"""
        raise NotImplementedError("Экран обязан реализовать метод get_settings_panel()!")

    # --- Опциональные методы (имеют реализацию по умолчанию) ---
    def update_settings_ui(self, data):
        """Обновляет элементы интерфейса при загрузке новых настроек"""
        pass 

    def apply_theme(self, palette):
        """Применяет цветовую палитру к интерфейсу"""
        pass
        
    def restore_layout_state(self, state_dict):
        """Восстанавливает сохраненные размеры панелей"""
        pass

    def get_layout_state(self):
        """Возвращает словарь с размерами панелей для сохранения"""
        return {}