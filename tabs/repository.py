from tabs.models import Task
from tabs.database import DatabaseManager

class TaskRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        # Храним состояние задач здесь, а не в графическом интерфейсе
        self._tasks = self.db.load_tasks()

    def get_all(self) -> list[Task]:
        """Возвращает список всех задач."""
        return self._tasks

    def get_by_id(self, task_id: str) -> Task:
        """Находит конкретную задачу по ID."""
        return next((t for t in self._tasks if getattr(t, "id", None) == task_id), None)

    def add(self, task: Task):
        """Добавляет новую задачу и сразу сохраняет базу."""
        self._tasks.append(task)
        self._save()

    def update(self, task: Task):
        """Обновляет существующую задачу по ID."""
        for i, t in enumerate(self._tasks):
            if getattr(t, "id", None) == task.id:
                self._tasks[i] = task
                break
        self._save()

    def delete(self, task_id: str):
        """Удаляет задачу по ID."""
        self._tasks = [t for t in self._tasks if getattr(t, "id", None) != task_id]
        self._save()

    def force_reload(self):
        """Принудительно перезагружает данные из БД (например, после скачивания из облака)."""
        self._tasks = self.db.load_tasks()

    def _save(self):
        """Внутренний метод сохранения. Интерфейс о нем знать не должен."""
        self.db.save_tasks(self._tasks)