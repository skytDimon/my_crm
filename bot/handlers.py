import re
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from .models import Project, Task, TaskStatus

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мои проекты", callback_data="my_projects")],
        [InlineKeyboardButton(text="Добавить проект", callback_data="add_project")]
    ])
    await message.answer("Добро пожаловать в систему учета проектов и задач! Выберите действие:", reply_markup=keyboard)

@router.message(F.text.startswith("+задача"))
async def add_task(message: Message, session: AsyncSession):
    # Разбор строки "+задача [Имя проекта] [Текст задачи]"
    match = re.match(r'^\+задача\s+\[(.*?)\]\s+(.*)$', message.text, re.IGNORECASE)
    if not match:
        await message.answer("Неверный формат. Используйте:\n<code>+задача [Имя проекта] [Текст задачи]</code>")
        return
    
    project_name = match.group(1).strip()
    task_desc = match.group(2).strip()

    result = await session.execute(select(Project).where(Project.name == project_name))
    project = result.scalar_one_or_none()

    if not project:
        await message.answer(f"Проект <b>{project_name}</b> не найден.")
        return

    new_task = Task(project_id=project.id, description=task_desc, status=TaskStatus.waiting)
    session.add(new_task)
    await session.commit()
    
    await message.answer(f"Задача добавлена в проект <b>{project_name}</b>.")

@router.message(F.text.startswith("+оплата"))
async def add_payment(message: Message, session: AsyncSession):
    # Разбор строки "+оплата [Имя проекта] [Сумма]"
    match = re.match(r'^\+оплата\s+\[(.*?)\]\s+(\d+(?:\.\d+)?)$', message.text, re.IGNORECASE)
    if not match:
        await message.answer("Неверный формат. Используйте:\n<code>+оплата [Имя проекта] [Сумма]</code>")
        return
    
    project_name = match.group(1).strip()
    amount = float(match.group(2).strip())

    result = await session.execute(select(Project).where(Project.name == project_name))
    project = result.scalar_one_or_none()

    if not project:
        await message.answer(f"Проект <b>{project_name}</b> не найден.")
        return

    project.paid_amount += amount
    await session.commit()
    
    await message.answer(f"Оплата {amount} добавлена к проекту <b>{project_name}</b>.\nВсего оплачено: {project.paid_amount} / {project.total_price}")
