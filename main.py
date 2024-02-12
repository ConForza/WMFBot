# Imports
from interactions import *
import requests
import json
from datetime import datetime, timedelta
import asyncio
import os

# Keys
APPLICATION_ID = os.environ.get("APPLICATION_ID")
PUBLIC_KEY = os.environ.get("PUBLIC_KEY")
TOKEN = os.environ.get("TOKEN")
GUILD_ID = os.environ.get("GUILD_ID")
INVOICE_GUILD = os.environ.get("INVOICE_GUILD")
TODO_GUILD = os.environ.get("TODO_GUILD")
API_URL = os.environ.get("API_URL")
USER_NAME = os.environ.get("USER_NAME")
API_KEY = os.environ.get("API_KEY")
email = ""
lesson_lengths = ["30", "60", "1 Hour"]
instrument_list = [
    "bass",
    "clarinet",
    "drums",
    "flute",
    "guitar",
    "mandolin",
    "piano",
    "saxophone",
    "singing",
    "ukulele",
    "violin",
    "bass guitar",
    "drum",
    "music theory",
    "sax"
]

headers = {
    "accept": "application/json",
    "content-type": "application/json"
}

today_date = datetime.today().strftime('%d-%m-%Y')

# Retrieve certificate codes from file
with open("codes.json", mode="r") as file:
    price_list = json.load(file)


# Function to calculate the number of lessons remaining for a given student
def lessons_remaining(email, instrument, lesson_length):
    lessons_remain = 0
    for certificate in check_certificates(email.lower(), f"{instrument.lower()}{lesson_length}", lesson_length):
        lessons_remain += certificate["remainingMinutes"]
    return lessons_remain // int(lesson_length)

# Function to create a direct messaging channel on Discord between bot and user
def create_dm_channel(user_id):
    data = {"recipient_id": user_id}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bot {TOKEN}"
    }
    r = requests.post('https://discord.com/api/v10/users/@me/channels', json=data, headers=headers)

    channel_id = r.json()["id"]
    return channel_id

# Check for valid payment certificates on the system
def check_certificates(email, product_id, lesson_length):
    valid_certificates = []

    parameters = {
        "email": email,
    }

    response = requests.get(
        url=API_URL + "certificates",
        auth=(USER_NAME, API_KEY),
        params=parameters,
        headers=headers
    )
    for certificate in response.json():
        if int(certificate["remainingMinutes"]) > 0:
            if str(certificate["productID"]) == price_list[product_id]:
                if lesson_length in certificate["name"]:
                    if datetime.strptime(certificate["expiration"], "%Y-%m-%d") >= datetime.now():
                        valid_certificates.append(certificate)
                elif "1 Hour" in certificate["name"]:
                    if datetime.strptime(certificate["expiration"], "%Y-%m-%d") >= datetime.now():
                        valid_certificates.append(certificate)

    return valid_certificates[::-1]

# Check out unpaid lessons using valid certificates
def check_past_codes(email, instrument, product_id, lesson_length):
    valid_certificates = check_certificates(email, product_id, lesson_length)

    unpaid_lessons = []
    parameters = {
        "email": email,
        "minDate": (datetime.now() - timedelta(days=90)).strftime("%B %d, %Y"),
        "maxDate": datetime.now().strftime("%B %d, %Y")
    }

    response = requests.get(
        url=API_URL + "appointments",
        auth=(USER_NAME, API_KEY),
        params=parameters,
        headers=headers
    )
    for appointment in response.json():
        if instrument in appointment["type"].lower() and lesson_length in appointment["type"].lower():
            if not (appointment["paid"] == "yes" or appointment["certificate"]):
                unpaid_lessons.append(appointment)

    if unpaid_lessons:
        for lesson in unpaid_lessons:
            lesson["datetime"] = datetime.strptime((lesson["date"] + lesson["time"]), "%B %d, %Y%H:%M")
        sorted_list = sorted(unpaid_lessons, key=lambda d: d["datetime"])
        counter = 0
        for certificate in valid_certificates:
            while certificate["remainingMinutes"] > 0 and counter < len(sorted_list):
                lesson = sorted_list[counter]
                lesson_id = lesson["id"]
                parameters = {
                    "certificate": certificate["certificate"],
                }
                requests.put(url=f"{API_URL}appointments/{lesson_id}?admin=true", auth=(USER_NAME, API_KEY),
                             json=parameters, headers=headers)
                certificate["remainingMinutes"] -= int(lesson_length)
                counter += 1

# Check to see if email is present on the system
def search_email(email):
    parameters = {
        "search": email
    }

    email_valid = False

    response = requests.get(
        url=API_URL + "clients",
        auth=(USER_NAME, API_KEY),
        params=parameters,
        headers=headers
    )

    for result in response.json():
        if email.lower() == result["email"].lower():
            email_valid = True
            break

    return email_valid

# List unpaid lessons for student
def check_unpaid_lessons(email):
    unpaid_lessons = []
    parameters = {
        "email": email,
        "minDate": (datetime.now() - timedelta(days=90)).strftime("%B %d, %Y"),
        "maxDate": datetime.now().strftime("%B %d, %Y")
    }

    response = requests.get(
        url=API_URL + "appointments",
        auth=(USER_NAME, API_KEY),
        params=parameters,
        headers=headers
    )
    for appointment in response.json():
        if not (appointment["paid"] == "yes" or appointment["certificate"]):
            unpaid_lessons.append(appointment)

    return unpaid_lessons


bot = Client(token=TOKEN)

# Bot sends ready status
@bot.event
async def on_ready():
    print("Ready!")


# Create modal form to add a new block of lessons for given student
@bot.command(name="add_block",
             description="Add a block",
             scope=GUILD_ID)
async def send_modal(ctx: CommandContext):
    modal = Modal(
        custom_id="add_block",
        title="Add a Block",
        components=[
            TextInput(
                style=TextStyleType.SHORT,
                custom_id="modal_email",
                label="Email address"
            ),
            TextInput(
                style=TextStyleType.SHORT,
                custom_id="modal_instrument",
                label="Instrument (e.g. guitar, singing)"
            ),
            TextInput(
                style=TextStyleType.SHORT,
                custom_id="modal_lesson_length",
                label="Lesson length (mins) - 30 or 60?",
                max_length=2
            ),
            TextInput(
                style=TextStyleType.SHORT,
                custom_id="modal_payment",
                label="Payment method - 'cash' or 'card'?",
                max_length=4
            )
        ]
    )
    await ctx.popup(modal)


# Create modal to calculate lessons remaining
@bot.command(name="lessons_remain",
             description="Calculates the lessons remaining on a block",
             scope=GUILD_ID)
async def send_modal1(ctx: CommandContext):
    modal = Modal(
        custom_id="lessons_remain",
        title="Number of block lessons remaining",
        components=[
            TextInput(
                style=TextStyleType.SHORT,
                custom_id="modal_email1",
                label="Email address"
            ),
            TextInput(
                style=TextStyleType.SHORT,
                custom_id="modal_instrument1",
                label="Instrument (e.g. guitar, singing)"
            ),
            TextInput(
                style=TextStyleType.SHORT,
                custom_id="modal_lesson_length1",
                label="Lesson length (mins) - 30 or 60?",
                max_length=2
            )
        ]
    )
    await ctx.popup(modal)

# Create modal to devise invoice for staff member
@bot.command(name="invoice",
             description="Creates an invoice for the staff member",
             scope=GUILD_ID)
async def send_modal2(ctx: CommandContext):
    modal = Modal(
        custom_id="invoice",
        title="Create invoice",
        components=[
            TextInput(
                style=TextStyleType.SHORT,
                custom_id="date_from",
                label="Date from (dd/mm/yy)",
                max_length=8
            ),
            TextInput(
                style=TextStyleType.SHORT,
                custom_id="date_to",
                label="Date to (dd/mm/yy)",
                max_length=8
            ),
        ]
    )
    await ctx.popup(modal)

# Use inputted details to add a new block of lessons
@bot.modal("add_block")
async def modal(ctx, modal_email: str, modal_instrument: str, modal_lesson_length: str, modal_payment: str):
    await ctx.defer()
    await asyncio.sleep(2)
    instrument_match = False
    for instrument in instrument_list:
        if modal_instrument.lower() == instrument:
            instrument_match = True
            break
    if search_email(modal_email.lower()) and (modal_lesson_length in lesson_lengths) and instrument_match:

        parameters = {
            "productID": price_list[f"{modal_instrument.lower()}{modal_lesson_length}"],
            "email": modal_email.lower()
        }

        response = requests.post(url=API_URL + "certificates",
                                 auth=(USER_NAME, API_KEY),
                                 json=parameters,
                                 headers=headers)

        if response.json():
            data = response.json()
            log = {
                "date": today_date,
                "certificate code": data["certificate"],
                "type": data["name"],
                "email": data["email"],
                "payment": modal_payment
            }
            with open("logs.json", mode="a") as file:
                file.write(str(log) + "\n")

            print(response.json())

        check_past_codes(modal_email, modal_instrument.lower()[0:2],
                         f"{modal_instrument.lower()}{modal_lesson_length}", modal_lesson_length)
        lessons_remain = lessons_remaining(modal_email.lower(), modal_instrument.lower(), modal_lesson_length)
        if response.ok:
            await ctx.send(
                f"Block created for {modal_email}: 5x{modal_lesson_length}min {modal_instrument.lower()}. {modal_payment.title()} payment. {lessons_remain} lessons remaining.")
        else:
            await ctx.send("Block could not be created.")
    else:
        await ctx.send("There has been a problem. Please check the details and try again.")

# Use inputted details to calculate the lessons remaining for a given student
@bot.modal("lessons_remain")
async def modal1(ctx, modal_email1: str, modal_instrument1: str, modal_lesson_length1: str):
    await ctx.defer(ephemeral=True)
    await asyncio.sleep(2)
    instrument_match = False
    for instrument in instrument_list:
        if instrument.lower() == instrument:
            instrument_match = True
            break
    if search_email(modal_email1.lower()) and (modal_lesson_length1 in lesson_lengths) and instrument_match:
        check_past_codes(modal_email1, modal_instrument1.lower()[0:2],
                         f"{modal_instrument1.lower()}{modal_lesson_length1}", modal_lesson_length1)
        lessons_remain = lessons_remaining(modal_email1.lower(), modal_instrument1.lower(), modal_lesson_length1)
        if lessons_remain > 0:
            await ctx.send(f"{modal_email1} has {lessons_remain} lessons remaining.")
        else:
            lessons_to_pay = len(check_unpaid_lessons(modal_email1))
            if lessons_to_pay:
                await ctx.send(f"{modal_email1} needs to pay for {lessons_to_pay} lessons.")
            else:
                await ctx.send(f"{modal_email1} has no remaining lessons and is due to pay now.")
    else:
        await ctx.send("There has been a problem. Please check the details and try again.", ephemeral=True)

# Work out lessons worked for staff member, matching it with their discord account. Calculate total amount owed.
@bot.modal("invoice")
async def modal2(ctx: CommandContext, date_from: str, date_to: str):
    global invoice
    global students_to_pay
    discord_user = ctx.author.user.id._snowflake
    appointments = []
    short_date_from = date_from
    short_date_to = date_to
    date_from = datetime.strptime(date_from, "%d/%m/%y").strftime("%B %d, %Y")
    date_to = datetime.strptime(date_to, "%d/%m/%y").strftime("%B %d, %Y")
    amount = 0
    total_amount = 0
    students_to_pay = []
    with open("staff_details.json", mode="r") as file:
        staff_details = json.load(file)
        for staff in staff_details:
            if staff["discord"] == discord_user:
                parameters = {
                    "minDate": date_from,
                    "maxDate": date_to,
                    "calendarID": staff["calendar"]
                }

                data = requests.get(url="https://acuityscheduling.com/api/v1/appointments",
                                    auth=(USER_NAME, API_KEY),
                                    params=parameters,
                                    headers=headers)

                results = data.json()
                for result in results:
                    appointments.append({
                        "date": result["date"],
                        "type": result["type"],
                        "first name": result["firstName"],
                        "surname": result["lastName"],
                        "email": result["email"],
                        "certificate": result["certificate"],
                        "cost": result["priceSold"],
                        "paid": result["paid"]
                    })

                appointments = appointments[::-1]

                invoice = f"Invoice for {ctx.author.user.username} between {short_date_from} and {short_date_to}\n\n"

                for appointment in appointments:
                    if appointment["certificate"] and appointment["certificate"].lower() == "taster":
                        amount = 7
                    elif appointment["cost"] == "16.00":
                        amount = 8.8
                    elif appointment["cost"] == "30.00":
                        amount = 17.60

                    if appointment["paid"] == "yes":
                        appointment["paid"] = "\U00002705"
                    else:
                        with open("exempt_students.txt", mode="r") as file:
                            exempt_students = [line[:-1] for line in file.readlines()]
                        if not appointment["email"] in exempt_students:
                            unpaid_lessons = [unpaid_lesson["date"] for unpaid_lesson in check_unpaid_lessons(appointment["email"])][::-1]
                            students_to_pay.append(
                                f"{appointment['date']}\n*{appointment['first name']} {appointment['surname']}*, email: {appointment['email']}, unpaid lessons({len(unpaid_lessons)}): {unpaid_lessons}")
                            appointment["paid"] = "\U0000274C"
                        else:
                            appointment["paid"] = "\U00002705"

                    appointment["amount"] = amount
                    total_amount += amount
                    invoice += f'{datetime.strptime(appointment["date"], "%B %d, %Y").strftime("%d/%m")} {appointment["first name"]} {appointment["surname"]} £{appointment["amount"]:.2f} {appointment["paid"]}\n'

                invoice += f"\nTotal = £{total_amount:.2f}"

                button = Button(
                    style=ButtonStyle.PRIMARY,
                    custom_id="send_invoice",
                    label="Send"
                )
                await ctx.send(invoice, ephemeral=True, components=button)

# Send invoice to invoice guild
@bot.component("send_invoice")
async def send_invoice(ctx: ComponentContext):
    discord_user = ctx.author.user.id._snowflake
    channel_id = create_dm_channel(discord_user)
    header = {
        "Content-Type": "application/json",
        "Authorization": f"Bot {TOKEN}"
    }
    discord_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    parameters = {
        "content": f"{invoice}\n*"
    }

    requests.post(url=discord_url, json=parameters, headers=header)

    channel_id = INVOICE_GUILD
    discord_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    requests.post(url=discord_url, json=parameters, headers=header)

    if students_to_pay:
        for student in students_to_pay:
            parameters = {
                "content": f"{student}"
            }
            channel_id = TODO_GUILD
            discord_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
            requests.post(url=discord_url, json=parameters, headers=header)

    await ctx.send("Invoice sent!", ephemeral=True)

# Initialise bot
bot.start()
