import os
import csv
import glob
import json
from django.contrib import admin
from unfold.admin import ModelAdmin
from django.utils.html import format_html
from django.contrib import messages
from django.conf import settings
from django.urls import path
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone

from .models import CSVFile, CSVData


@admin.register(CSVFile)
class CSVFileAdmin(ModelAdmin):
    list_display = [
        'filename',
        'file_status',
        'file_size',
        'row_count',
        'upload_date',
        'custom_actions'
    ]
    list_filter = ['status', 'upload_date']
    search_fields = ['filename']
    readonly_fields = [
        'filename',
        'upload_date',
        'processed_date',
        'row_count',
        'error_message',
        'file_info'
    ]

    # actions должен быть списком строк с названиями методов
    actions = ['process_selected_files_action']

    def get_queryset(self, request):
        """Автоматическое сканирование файлов при загрузке списка"""
        self.scan_csv_files()
        return super().get_queryset(request)

    def scan_csv_files(self):
        """Сканирует корневую директорию проекта на наличие CSV файлов"""
        csv_files = glob.glob(os.path.join(settings.BASE_DIR, "*.csv"))

        for csv_path in csv_files:
            filename = os.path.basename(csv_path)
            # Создаем запись только если файл еще не в базе
            if not CSVFile.objects.filter(filename=filename).exists():
                CSVFile.objects.create(filename=filename)

    def file_status(self, obj):
        """Красивое отображение статуса с иконками"""
        status_config = {
            'pending': ('⚪', 'gray', 'Ожидает'),
            'processing': ('🟡', 'orange', 'В обработке'),
            'completed': ('🟢', 'green', 'Завершено'),
            'error': ('🔴', 'red', 'Ошибка'),
        }

        icon, color, text = status_config.get(obj.status, ('⚪', 'gray', 'Неизвестно'))

        return format_html(
            '<span style="color: {};">{} {}</span>',
            color,
            icon,
            text
        )

    file_status.short_description = "Статус"

    def file_size(self, obj):
        """Отображает размер файла"""
        return obj.get_file_size()

    file_size.short_description = "Размер файла"

    def custom_actions(self, obj):
        """Кнопки действий для каждой строки (переименовано чтобы не конфликтовать с actions)"""
        buttons = []

        if obj.status in ['pending', 'error'] and obj.file_exists:
            buttons.append(
                format_html(
                    '<a href="{}" class="button" style="background: #4CAF50; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px; margin-right: 5px;">📥 Импорт</a>',
                    f'{obj.id}/process/'
                )
            )

        if obj.status == 'completed':
            buttons.append(
                format_html(
                    '<a href="{}" class="button" style="background: #2196F3; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px; margin-right: 5px;">👁️ Просмотр</a>',
                    f'../csvdata/?csv_file__id__exact={obj.id}'
                )
            )

        # Кнопка переимпорта для завершенных файлов
        if obj.status == 'completed' and obj.file_exists:
            buttons.append(
                format_html(
                    '<a href="{}" class="button" style="background: #FF9800; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px; margin-right: 5px;">🔄 Повтор</a>',
                    f'{obj.id}/process/'
                )
            )

        if not obj.file_exists:
            buttons.append(
                format_html(
                    '<span style="color: red; padding: 5px 10px;">❌ Файл удален</span>'
                )
            )

        # Кнопка удаления данных
        if obj.status == 'completed':
            buttons.append(
                format_html(
                    '<a href="{}" class="button" style="background: #f44336; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px;" onclick="return confirm(\'Удалить все данные для этого файла?\')">🗑️ Очистить</a>',
                    f'{obj.id}/delete_data/'
                )
            )

        return format_html(''.join(buttons)) if buttons else "-"

    custom_actions.short_description = "Действия"

    def file_info(self, obj):
        """Дополнительная информация о файле в детальном просмотре"""
        if not obj.file_exists:
            return format_html('<p style="color: red;">⚠️ Файл не найден на диске</p>')

        info_lines = [
            f"Полный путь: {obj.full_path}",
            f"Размер: {obj.get_file_size()}",
            f"Существует: {'Да' if obj.file_exists else 'Нет'}",
        ]

        return format_html('<pre>{}</pre>', '\n'.join(info_lines))

    file_info.short_description = "Информация о файле"

    def process_selected_files_action(self, request, queryset):
        """Действие для массовой обработки выбранных файлов"""
        success_count = 0
        error_count = 0

        for csv_file in queryset:
            try:
                if not csv_file.file_exists:
                    self.message_user(request, f"Файл {csv_file.filename} не найден", messages.ERROR)
                    error_count += 1
                    continue

                # Импортируем данные
                imported_rows = self.import_csv_data(csv_file)

                csv_file.status = 'completed'
                csv_file.row_count = imported_rows
                csv_file.processed_date = timezone.now()
                csv_file.save()

                success_count += 1
                self.message_user(request, f"✅ Успешно импортировано {imported_rows} строк из {csv_file.filename}",
                                  messages.SUCCESS)

            except Exception as e:
                csv_file.status = 'error'
                csv_file.error_message = str(e)
                csv_file.save()
                error_count += 1
                self.message_user(request, f"❌ Ошибка при обработке {csv_file.filename}: {str(e)}", messages.ERROR)

        if success_count:
            self.message_user(request, f"Обработано файлов: {success_count}", messages.SUCCESS)
        if error_count:
            self.message_user(request, f"Ошибок: {error_count}", messages.ERROR)

    process_selected_files_action.short_description = "Импортировать выбранные CSV файлы"

    def process_csv_view(self, request, object_id):
        """Обработка одного CSV файла"""
        try:
            csv_file = CSVFile.objects.get(id=object_id)

            # Проверяем существование файла
            if not csv_file.file_exists:
                messages.error(request, f"Файл {csv_file.filename} не найден на диске")
                return HttpResponseRedirect(reverse('admin:csv_importer_csvfile_changelist'))

            # Обновляем статус
            csv_file.status = 'processing'
            csv_file.error_message = ''
            csv_file.save()

            # Импортируем данные
            imported_rows = self.import_csv_data(csv_file)

            csv_file.status = 'completed'
            csv_file.row_count = imported_rows
            csv_file.processed_date = timezone.now()
            csv_file.save()

            messages.success(request, f"✅ Успешно импортировано {imported_rows} строк из {csv_file.filename}")

        except Exception as e:
            csv_file.status = 'error'
            csv_file.error_message = str(e)
            csv_file.save()
            messages.error(request, f"❌ Ошибка при обработке {csv_file.filename}: {str(e)}")

        return HttpResponseRedirect(reverse('admin:csv_importer_csvfile_changelist'))

    def delete_data_view(self, request, object_id):
        """Удаление данных для файла"""
        try:
            csv_file = CSVFile.objects.get(id=object_id)
            deleted_count, _ = CSVData.objects.filter(csv_file=csv_file).delete()

            csv_file.status = 'pending'
            csv_file.row_count = 0
            csv_file.error_message = ''
            csv_file.save()

            messages.success(request, f"✅ Удалено {deleted_count} записей для файла {csv_file.filename}")

        except Exception as e:
            messages.error(request, f"❌ Ошибка при удалении данных: {str(e)}")

        return HttpResponseRedirect(reverse('admin:csv_importer_csvfile_changelist'))

    def import_csv_data(self, csv_file):
        """Импортирует данные из CSV файла в базу данных"""
        try:
            with open(csv_file.full_path, 'r', encoding='utf-8') as file:
                return self._process_csv_file(csv_file, file)
        except UnicodeDecodeError:
            # Пробуем другие кодировки
            try:
                with open(csv_file.full_path, 'r', encoding='cp1251') as file:
                    return self._process_csv_file(csv_file, file)
            except UnicodeDecodeError:
                with open(csv_file.full_path, 'r', encoding='latin-1') as file:
                    return self._process_csv_file(csv_file, file)
        except Exception as e:
            raise Exception(f"Ошибка чтения файла: {str(e)}")

    def _process_csv_file(self, csv_file, file):
        """Вспомогательный метод для обработки CSV файла"""
        # Удаляем старые данные для этого файла
        CSVData.objects.filter(csv_file=csv_file).delete()

        csv_reader = csv.DictReader(file)
        data_rows = []

        for row_num, row in enumerate(csv_reader, 1):
            # Очищаем данные от лишних пробелов
            cleaned_row = {
                key.strip(): value.strip() if isinstance(value, str) else value
                for key, value in row.items()
                if key and key.strip()  # Игнорируем пустые колонки
            }

            # Пропускаем полностью пустые строки
            if not any(cleaned_row.values()):
                continue

            data_rows.append(CSVData(
                csv_file=csv_file,
                row_number=row_num,
                data=cleaned_row
            ))

        # Массовое сохранение для оптимизации
        if data_rows:
            CSVData.objects.bulk_create(data_rows)
        return len(data_rows)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/process/', self.admin_site.admin_view(self.process_csv_view), name='csv_process'),
            path('<path:object_id>/delete_data/', self.admin_site.admin_view(self.delete_data_view),
                 name='csv_delete_data'),
        ]
        return custom_urls + urls


@admin.register(CSVData)
class CSVDataAdmin(ModelAdmin):
    list_display = ['csv_file', 'row_number', 'preview_data', 'import_date']
    list_filter = ['csv_file', 'import_date']
    search_fields = ['data', 'csv_file__filename']
    readonly_fields = ['csv_file', 'row_number', 'data_preview', 'import_date']

    def preview_data(self, obj):
        """Краткий предпросмотр данных"""
        data_str = json.dumps(obj.data, ensure_ascii=False)
        preview = data_str[:100] + "..." if len(data_str) > 100 else data_str
        return format_html('<code style="font-size: 0.9em;">{}</code>', preview)

    preview_data.short_description = "Данные"

    def data_preview(self, obj):
        """Детальный предпросмотр данных в админке"""
        formatted_data = json.dumps(obj.data, ensure_ascii=False, indent=2)
        return format_html(
            '<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto; font-size: 0.9em;">{}</pre>',
            formatted_data
        )

    data_preview.short_description = "Полные данные"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True