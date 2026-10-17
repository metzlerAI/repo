import re
NEED = re.compile(r'Корпусная мебель|Мебель для кухни|Шкаф|Гардероб', re.I)
BAD_R = re.compile(r'Стройматериалы|Матрасы|Остекление|Стекло и зеркала|отделочные материалы|Ремонт помещений|Окна|Входные двери|гипермаркет', re.I)
BAD_N = re.compile(r'Лемана|Мегастрой|гипермаркет|Торговый комплекс|Ангстрем|Hoff|Леруа|IKEA|Шатура|Мария|Лазурит|Стильные кухни|Первая мебельная', re.I)
def ok(name, rubrics):
    return 'Мебель на заказ' in rubrics and bool(NEED.search(rubrics)) and not BAD_R.search(rubrics) and not BAD_N.search(name)
