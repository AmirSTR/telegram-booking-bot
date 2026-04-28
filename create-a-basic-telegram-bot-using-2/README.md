# Basic Telegram Bot

Simple Telegram bot in Python using `aiogram`, `SQLite`, and `SQLAlchemy`.

## Project structure

```text
.
|-- bot.py
|-- config.py
|-- handlers/
|   |-- admin.py
|   |-- booking.py
|   |-- menu.py
|   `-- start.py
|-- keyboards/
|   |-- admin.py
|   |-- booking.py
|   `-- main_menu.py
|-- states/
|   |-- admin.py
|   `-- booking.py
|-- scheduler/
|   `-- reminders.py
|-- database/
|   |-- base.py
|   |-- db.py
|   |-- models.py
|   |-- service_catalog.py
|   `-- bot.db
|-- requirements.txt
`-- .env.example
```

## Setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Create `.env` file based on `.env.example` and add your values:

```env
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_ID=your_admin_telegram_id_here
ADMIN_CHAT_ID=your_admin_chat_id_here
```

4. Run the bot:

```powershell
python bot.py
```

## Database

- SQLite database file is created automatically at `database/bot.db`
- Tables are created automatically on bot startup
- Services from `database/service_catalog.py` are added only if they do not exist yet
- Tables:
  - `users (id, name, username)`
  - `services (id, name, price, duration)`
  - `bookings (id, user_id, service_id, date, time, status)`

## Admin panel

- Open with `/admin`
- Access is allowed only for `ADMIN_ID`
- Buttons:
  - `Услуги`
  - `Записи`
  - `Доход`

### Admin functions

- View all bookings
- Add a new service
- Edit an existing service
- View income for today, week, and month

### Service input format

For adding or editing services, send:

```text
Название | Цена | Длительность
```

Example:

```text
Стрижка VIP | 2500 | 90
```

## Booking flow

1. User clicks `Записаться`
2. User selects a service
3. User selects a date from weekdays only
4. User selects a time generated from working hours and service duration
5. Bot checks that the slot is free and saves the booking to the database

## Waitlist

- If there are no available slots for the selected date, the bot offers `Встать в лист ожидания`
- The user is saved in the waitlist for the selected service and date
- When a slot becomes free, the bot notifies the first user in the queue

## Cancel flow

1. User clicks `Отменить запись`
2. User selects one of upcoming bookings
3. User confirms cancellation
4. Bot deletes the booking from the database and the slot becomes free

## Reschedule flow

1. User clicks `Перенести запись`
2. User selects one of upcoming bookings
3. User selects a new weekday date
4. User selects a new free time slot generated from service duration
5. Bot updates the booking in the database and the old slot becomes free

## Working schedule

- Working days: `Mon-Fri`
- Days off: `Sat/Sun`
- Working hours: `10:00-20:00`
- Available time slots are generated automatically based on the selected service duration
- Overlapping bookings are blocked even if services have different durations

## Reminders

- Background scheduler checks bookings every minute
- Background scheduler also marks finished bookings as completed
- Reminders are sent:
  - `24 hours before`
  - `3 hours before`
- Reminder message includes:
  - date
  - time
  - service
- Sent reminders are stored in the database so they are not duplicated after restart

## Confirmation

- Users can confirm a booking with the `Подтвердить запись` button
- Confirmed bookings are tracked in the database
- If `ADMIN_CHAT_ID` is set and a booking is still not confirmed close to the `3 hours before` reminder, the bot notifies the admin

## Completed bookings

- After the service time passes, the booking is marked as `completed` automatically
- Income in the admin panel is calculated from completed bookings
- Admin panel shows:
  - today income
  - weekly income
  - monthly income
