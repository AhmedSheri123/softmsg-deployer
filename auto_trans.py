import os
import polib
from googletrans import Translator
from django.conf import settings

def translate_text(text, dest_language='ar'):
    translator = Translator()
    try:
        # استخدم Google Translate لترجمة النص
        translation = translator.translate(text, dest=dest_language)
        return translation.text
    except Exception as e:
        print(f"Error translating text: {text}. Error: {e}")
        return None

def correct_fuzzy_entries(language_code):
    # تحديد مسار ملف .po للغة المعنية
    locale_path = os.path.join('F:/mostql/softmsg', 'locale', language_code, 'LC_MESSAGES', 'django.po')
    
    # التأكد من وجود الملف
    if not os.path.exists(locale_path):
        print(f"No translation file found for language: {language_code}")
        return
    
    # فتح ملف .po باستخدام polib
    po_file = polib.pofile(locale_path)
    
    # المرور على كل مدخل في ملف po
    for entry in po_file:
        
        # إذا كان المدخل يحتوي على العلامة fuzzy
        if 'fuzzy' in entry.flags :#or (entry.msgstr == '' and '.\\\\accounts' in str(entry.occurrences)):
            
            print(f"Translating fuzzy entry: {entry.msgid}")
            
            # ترجمة النص الأصلي msgid
            translated_text = translate_text(entry.msgid, language_code)
            
            if translated_text:
                # تحديث النص المترجم
                entry.msgstr = translated_text
                if 'fuzzy' in entry.flags:
                    # إزالة العلامة fuzzy
                    entry.flags.remove('fuzzy')
                print(f"Updated translation: {translated_text}")
            else:
                print(f"Failed to translate: {entry.msgid}")
    
    # حفظ التغييرات في ملف po
    po_file.save()

# حدد رمز اللغة الخاصة بك
language_codes = ['de', 'ro', 'ar', 'he']
for language_code in language_codes:
    # قم بتصحيح الترجمات fuzzy للغة العربية
    correct_fuzzy_entries(language_code)
