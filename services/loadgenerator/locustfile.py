#!/usr/bin/python
#
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Modified by the Antojo project, 2026

import random
from locust import FastHttpUser, TaskSet, between
from faker import Faker
import datetime
fake = Faker('es_MX')

# Antojo menu product IDs, grouped by meal.
lunch_dishes = ['TORTAHOGADA', 'TORTAMEDIA', 'LONCHEPIERNA', 'TACOSBARBACOA']
dinner_dishes = ['BIRRIACHIVO', 'CARNEJUGO', 'POZOLEROJO']
drinks = ['TEJUINO', 'AGUAJAMAICA']
desserts = ['JERICALLA', 'BIONICO']
products = lunch_dishes + dinner_dishes + drinks + desserts

def index(l):
    l.client.get("/")

def setCurrency(l):
    # Most Guadalajara customers stay in MXN; a few switch to test conversion.
    currencies = ['MXN', 'MXN', 'MXN', 'USD', 'EUR']
    l.client.post("/setCurrency",
        {'currency_code': random.choice(currencies)})

def browseProduct(l):
    l.client.get("/product/" + random.choice(products))

def viewCart(l):
    l.client.get("/cart")

def add(l, product, quantity):
    l.client.get("/product/" + product)
    l.client.post("/cart", {
        'product_id': product,
        'quantity': quantity})

def addToCart(l):
    add(l, random.choice(products), random.randint(1, 4))

def empty_cart(l):
    l.client.post('/cart/empty')

def place_order(l):
    current_year = datetime.datetime.now().year+1
    l.client.post("/cart/checkout", {
        'email': fake.email(),
        'street_address': fake.street_address(),
        'zip_code': random.randint(44100, 45250),
        'city': 'Guadalajara',
        'state': 'Jalisco',
        'country': 'México',
        'credit_card_number': fake.credit_card_number(card_type="visa"),
        'credit_card_expiration_month': random.randint(1, 12),
        'credit_card_expiration_year': random.randint(current_year, current_year + 70),
        'credit_card_cvv': f"{random.randint(100, 999)}",
    })

def checkout(l):
    addToCart(l)
    place_order(l)

def lunch_order(l):
    """A lunch rush order: a torta or tacos plus a drink."""
    add(l, random.choice(lunch_dishes), random.randint(1, 3))
    add(l, random.choice(drinks), random.randint(1, 3))
    place_order(l)

def dinner_order(l):
    """A family dinner: a caldo for several people plus dessert."""
    add(l, random.choice(dinner_dishes), random.randint(2, 5))
    add(l, random.choice(desserts), random.randint(1, 4))
    place_order(l)

def logout(l):
    l.client.get('/logout')  


class UserBehavior(TaskSet):

    def on_start(self):
        index(self)

    tasks = {index: 1,
        setCurrency: 2,
        browseProduct: 10,
        addToCart: 2,
        viewCart: 3,
        checkout: 1,
        lunch_order: 2,
        dinner_order: 1}

class WebsiteUser(FastHttpUser):
    tasks = [UserBehavior]
    wait_time = between(1, 10)
