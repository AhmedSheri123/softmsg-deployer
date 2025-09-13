from django.db import models
# Create your models here.







def get_discont_original_price_and_saved_money(price, discont):
    orginal = None
    if price and discont:
        orginal = (price/ (100-discont))*100
        return int(orginal), int(orginal-price)
    return orginal, None
