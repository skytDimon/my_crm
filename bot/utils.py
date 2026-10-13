from datetime import datetime
from .models import TaskStatus

def format_currency(amount: float) -> str:
    """Форматирует число в денежный вид, например: 150 000 ₽"""
    if amount is None:
        amount = 0.0
    if amount == int(amount):
        formatted = f"{int(amount):,}".replace(",", " ")
    else:
        formatted = f"{amount:,.2f}".replace(",", " ")
    return f"{formatted} ₽"

def render_progress_bar(paid: float, total: float, length: int = 10) -> str:
    """Генерирует аккуратный визуальный прогресс-бар оплаты"""
    if total <= 0:
        return "[──────────] 0%"
    
    pct = (paid / total) * 100
    fill = min(max(int((paid / total) * length), 0), length)
    empty = length - fill
    
    bar = "▓" * fill + "░" * empty
    return f"[{bar}] {pct:.1f}%"

def task_status_info(status: TaskStatus) -> tuple[str, str]:
    """Возвращает (emoji, русское название) статуса задачи"""
    if status == TaskStatus.waiting:
        return "⏳", "В ожидании"
    elif status == TaskStatus.in_progress:
        return "🔄", "В работе"
    elif status == TaskStatus.done:
        return "✅", "Выполнено"
    return "❓", str(status)

def format_datetime(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")
