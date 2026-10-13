from aiogram.fsm.state import State, StatesGroup

class AddProjectFSM(StatesGroup):
    name = State()
    client_name = State()
    total_price = State()

class AddTaskFSM(StatesGroup):
    description = State()

class AddPaymentFSM(StatesGroup):
    amount = State()

class SetHoursFSM(StatesGroup):
    hours = State()
