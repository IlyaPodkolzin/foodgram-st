import csv
import os
from django.core.management.base import BaseCommand
from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Команда импортирования ингредиентов из csv-файла'

    def handle(self, *args, **options):
        csv_file_path = os.path.join('data', 'ingredients.csv')

        with open(csv_file_path, encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                name, measurement_unit = row
                Ingredient.objects.get_or_create(
                    name=name,
                    measurement_unit=measurement_unit
                )

        self.stdout.write(
            self.style.SUCCESS('Загрузка ингредиентов успешно завершена')
        )
