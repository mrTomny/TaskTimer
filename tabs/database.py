import os
import json
import sqlite3
import uuid
from datetime import datetime
from dataclasses import asdict
from tabs.logger import log
from tabs.models import Task, HistoryEvent  # Обязательно импортируем HistoryEvent

class DatabaseManager:
    def __init__(self, db_file, data_file=None):
        self.db_file = db_file
        self.data_file = data_file
        self.setup_database()
        self.migrate_db_schema()  # Запускаем миграцию перед загрузкой старых JSON
        if self.data_file:
            self.migrate_json_to_sqlite()

    def setup_database(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # СОЗДАНИЕ НОВОЙ ТАБЛИЦЫ С УЧЕТОМ НОВОЙ АРХИТЕКТУРЫ (deadline и history)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                client TEXT,
                task TEXT,
                deadline TEXT,
                status TEXT,
                notes TEXT,
                completed_dates TEXT,
                color TEXT DEFAULT '',
                subtasks TEXT DEFAULT '[]',
                history TEXT DEFAULT '[]',
                time_spent INTEGER DEFAULT 0,
                active_since TEXT DEFAULT ''
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                task_text TEXT,
                hours REAL,
                color TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def migrate_db_schema(self):
        """Единожды конвертирует старую БД (с date/time и отдельной таблицей history) в новый формат"""
        with sqlite3.connect(self.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Проверяем, существует ли вообще таблица tasks (актуально для пустой БД или :memory:)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
            if not cursor.fetchone():
                return
            
            # Проверяем, в каком формате сейчас таблица
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [col['name'] for col in cursor.fetchall()]
            
            # Если колонка deadline уже есть, значит база обновлена
            if "deadline" in columns:
                return
                
            log.info("Начата миграция базы данных на новый формат (datetime и HistoryEvent)...")
            
            # Вытягиваем старые задачи
            cursor.execute("SELECT * FROM tasks")
            old_tasks = cursor.fetchall()
            
            # Вытягиваем старую историю из отдельной таблицы
            old_histories = {}
            try:
                cursor.execute("SELECT task_id, log_text FROM history")
                for row in cursor.fetchall():
                    tid = row['task_id']
                    if tid not in old_histories:
                        old_histories[tid] = []
                    old_histories[tid].append(row['log_text'])
            except sqlite3.OperationalError:
                pass # Таблицы history может и не быть
                
            # Переименовываем старую таблицу (оставляем как бэкап)
            cursor.execute("ALTER TABLE tasks RENAME TO tasks_old_backup")
            
            # Создаем новую чистую таблицу с правильными колонками
            self.setup_database()
            
            # Переносим и конвертируем данные
            for row in old_tasks:
                try:
                    deadline_dt = datetime.strptime(f"{row['date']} {row['time']}", "%d.%m.%Y %H:%M")
                except Exception:
                    deadline_dt = datetime.now()
                    
                task_id = row['id']
                task_history = old_histories.get(task_id, [])
                new_history = []
                for entry in task_history:
                    try:
                        ts_str = entry[1:20]
                        action_str = entry[22:]
                        event_dt = datetime.strptime(ts_str, "%d.%m.%Y %H:%M:%S")
                        new_history.append({"timestamp": event_dt.isoformat(), "action": action_str, "details": ""})
                    except Exception:
                        new_history.append({"timestamp": datetime.now().isoformat(), "action": str(entry), "details": ""})
                        
                cursor.execute('''
                    INSERT INTO tasks (id, client, task, deadline, status, notes, completed_dates, color, subtasks, history, time_spent, active_since)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['id'], row['client'], row['task'], deadline_dt.isoformat(), row['status'], 
                    row['notes'], row['completed_dates'], row['color'], row['subtasks'], 
                    json.dumps(new_history), row['time_spent'], row['active_since']
                ))
                
            cursor.execute("DROP TABLE IF EXISTS history")
            conn.commit()
            log.info("Миграция базы данных успешно завершена!")

    def migrate_json_to_sqlite(self):
        if not self.data_file or not os.path.exists(self.data_file):
            return 
            
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM tasks")
        if cursor.fetchone()[0] == 0:
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    old_tasks = json.load(f)
                    
                for t in old_tasks:
                    task_id = t.get('id', str(uuid.uuid4()))
                    
                    # Конвертируем дату/время для новой схемы
                    deadline_str = f"{t.get('date', '')} {t.get('time', '')}".strip()
                    try:
                        deadline_dt = datetime.strptime(deadline_str, "%d.%m.%Y %H:%M")
                    except Exception:
                        deadline_dt = datetime.now()
                        
                    # Конвертируем историю
                    history_events = [{"timestamp": datetime.now().isoformat(), "action": h, "details": ""} for h in t.get('history', [])]
                    
                    cursor.execute('''
                        INSERT INTO tasks (id, client, task, deadline, status, notes, completed_dates, color, history)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        task_id, t.get('client', ''), t.get('task', ''), deadline_dt.isoformat(), 
                        t.get('status', 'Ожидание'), t.get('notes', ''), json.dumps(t.get('completed_dates', [])), 
                        t.get('color', ''), json.dumps(history_events)
                    ))
                
                conn.commit()
                os.rename(self.data_file, self.data_file + ".migrated")
            except Exception as e:
                log.error(f"Ошибка при миграции JSON в SQLite: {e}")
                
        conn.close()

    def save_tasks(self, tasks_data: list[Task]):
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Удаляем старые записи
            current_ids = [t.id for t in tasks_data]
            if current_ids:
                placeholders = ','.join('?' for _ in current_ids)
                cursor.execute(f"DELETE FROM tasks WHERE id NOT IN ({placeholders})", current_ids)
            else:
                cursor.execute("DELETE FROM tasks")
            
            # Сохраняем актуальные
            for t in tasks_data:
                # Конвертируем список датаклассов HistoryEvent в JSON
                history_json = json.dumps([
                    {"timestamp": h.timestamp.isoformat(), "action": h.action, "details": h.details} 
                    for h in t.history
                ])
                
                cursor.execute('''
                    REPLACE INTO tasks (id, client, task, deadline, status, notes, completed_dates, color, subtasks, history, time_spent, active_since)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    t.id, t.client, t.task, t.deadline.isoformat(), t.status, t.notes, 
                    json.dumps(t.completed_dates), t.color, 
                    json.dumps(t.subtasks), history_json, t.time_spent, t.active_since
                ))
                
            conn.commit()
            conn.close()
        except Exception as e: 
            log.error(f"Ошибка сохранения в БД: {e}")

    def load_tasks(self) -> list[Task]:
        tasks_data = []
        if not os.path.exists(self.db_file):
            return tasks_data
            
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT id, client, task, deadline, status, notes, completed_dates, color, subtasks, history, time_spent, active_since FROM tasks")
            
            for row in cursor.fetchall():
                # Парсим JSON истории в объекты HistoryEvent
                history_raw = json.loads(row[9]) if row[9] else []
                history_events = []
                for h in history_raw:
                    try:
                        ts = datetime.fromisoformat(h['timestamp'])
                        history_events.append(HistoryEvent(timestamp=ts, action=h['action'], details=h.get('details', '')))
                    except Exception:
                        pass
                
                task_obj = Task(
                    id=row[0],
                    client=row[1] if row[1] else "",
                    task=row[2] if row[2] else "",
                    deadline=datetime.fromisoformat(row[3]) if row[3] else datetime.now(),
                    status=row[4] if row[4] else "Ожидание",
                    notes=row[5] if row[5] else "",
                    completed_dates=json.loads(row[6]) if row[6] else [],
                    color=row[7] if row[7] else "",
                    subtasks=json.loads(row[8]) if row[8] else [],
                    history=history_events,
                    time_spent=row[10] if row[10] else 0,
                    active_since=row[11] if row[11] else ""
                )
                tasks_data.append(task_obj)
                
            conn.close()
        except Exception as e: 
            log.error(f"Ошибка чтения из БД: {e}")
            
        return tasks_data

    # ================= УПРАВЛЕНИЕ ШАБЛОНАМИ И ЗАМЕТКАМИ НИЖЕ (БЕЗ ИЗМЕНЕНИЙ) =================
    def get_templates(self):
        if not os.path.exists(self.db_file): return []
        try:
            with sqlite3.connect(self.db_file) as conn:
                return conn.execute("SELECT id, name, task_text, hours, color FROM templates").fetchall()
        except Exception as e:
            log.error(f"Ошибка загрузки шаблонов: {e}")
            return []

    def add_template(self, name, task_text, hours, color):
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute("INSERT INTO templates (name, task_text, hours, color) VALUES (?, ?, ?, ?)", 
                             (name, task_text, hours, color))
        except Exception as e:
            log.error(f"Ошибка сохранения шаблона: {e}")

    def update_template(self, t_id, name, task_text, hours, color):
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute("UPDATE templates SET name=?, task_text=?, hours=?, color=? WHERE id=?", 
                             (name, task_text, hours, color, t_id))
        except Exception as e:
            log.error(f"Ошибка обновления шаблона: {e}")

    def delete_template(self, t_id):
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute("DELETE FROM templates WHERE id=?", (t_id,))
        except Exception as e:
            log.error(f"Ошибка удаления шаблона: {e}")

    def get_notes(self):
        if not os.path.exists(self.db_file): return []
        try:
            with sqlite3.connect(self.db_file) as conn:
                return conn.execute("SELECT id, title, content FROM notes").fetchall()
        except Exception as e:
            log.error(f"Ошибка загрузки заметок: {e}")
            return []

    def add_note(self, title, content=""):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO notes (title, content) VALUES (?, ?)", (title, content))
                return cursor.lastrowid
        except Exception as e:
            log.error(f"Ошибка создания заметки: {e}")
            return None

    def update_note_content(self, note_id, content):
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute("UPDATE notes SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                             (content, note_id))
        except Exception as e:
            log.error(f"Ошибка сохранения контента заметки: {e}")

    def update_note_title(self, note_id, title):
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute("UPDATE notes SET title = ? WHERE id = ?", (title, note_id))
        except Exception as e:
            log.error(f"Ошибка переименования заметки: {e}")

    def delete_note(self, note_id):
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        except Exception as e:
            log.error(f"Ошибка удаления заметки: {e}")