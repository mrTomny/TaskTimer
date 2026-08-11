from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class HistoryEvent:
    timestamp: datetime
    action: str
    details: str = "" 
    # В details можно удобно хранить путь к скриншоту, 
    # старые/новые даты при переносе или любые доп. данные,
    # не ломая при этом основную строку action.

@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client: str = ""
    task: str = ""
    deadline: datetime = field(default_factory=datetime.now) # Заменяет date и time
    status: str = "Ожидание"
    time_spent: int = 0
    color: str = ""
    notes: str = ""
    history: list[HistoryEvent] = field(default_factory=list) # Теперь это список объектов!
    subtasks: list[dict] = field(default_factory=list) 
    completed_dates: list[str] = field(default_factory=list)
    active_since: str = ""