import requests, json

def auth():
    u = 'https://restapi.paylink.sa/api/auth'

    data = {
        "apiId":"APP_ID_1681303723036",
        "secretKey":"e6b717d3-62ff-4f8c-a451-4194c2c5d55a",
        "persistToken":"false"
    }

    r = requests.post(u, json=data)
    return r.json()


def addInvoice(orderID, total_price_amount, email, phone, clientName, ser_title, ser_disc, callBackUrl, cancelUrl, currency='USD'):
        
    id_token = auth().get('id_token')
    if id_token:
        u = "https://restapi.paylink.sa/api/addInvoice"
        
        data = {
            "orderNumber": orderID,
            "amount": total_price_amount,
            "callBackUrl": callBackUrl,
            "cancelUrl": cancelUrl,
            "clientName": clientName,
            "clientEmail": email,
            "clientMobile": phone,
            "currency": currency,
            "products": [
                {
                "title": ser_title,
                "price": total_price_amount,
                "qty": 1,
                "description": ser_disc,
                "isDigital": False,
                "imageSrc": None,
                }
            ],
            "supportedCardBrands": [
                "mada",
                "visaMastercard",
                "amex",
                "tabby",
                "tamara",
                "stcpay",
                "urpay"
            ],
            "displayPending": True,
            "note": "Example invoice"
            }
        
        headers = {
                "Authorization": f"Bearer {id_token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
        }
        r = requests.post(u, headers=headers, json=data)

        return r.json()
    return None


def getInvoice(orderID):
    id_token = auth().get('id_token')
    if id_token:
        u = f"https://restapi.paylink.sa/api/getInvoice/{orderID}"
        headers = {
                "Authorization": f"Bearer {id_token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
        }
        r = requests.get(u, headers=headers)
    return r.json()
