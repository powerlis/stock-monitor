import firebase_admin
from firebase_admin import credentials, firestore


FIREBASE_KEY_FILE = "firebase-service-key.json"

component_stocks = [
    {"rank": 1, "type": "COMPONENT", "name": "Inovance Technology(회천기술)", "code": "300124.SZ", "weight": 0.09, "market": "중국 심천"},
    {"rank": 2, "type": "COMPONENT", "name": "UBTECH Robotics(유비테크 로보틱스)", "code": "9880.HK", "weight": 0.0836, "market": "홍콩"},
    {"rank": 3, "type": "COMPONENT", "name": "Ningbo Tuopu Group(탁보그룹)", "code": "601689.SH", "weight": 0.082, "market": "중국 상해"},
    {"rank": 4, "type": "COMPONENT", "name": "DOBOT(도봇)", "code": "2432.HK", "weight": 0.0638, "market": "홍콩"},
    {"rank": 5, "type": "COMPONENT", "name": "Leader Harmonious Drive Systems(녹적해파)", "code": "688017.SH", "weight": 0.0606, "market": "중국 상해"},
    {"rank": 6, "type": "COMPONENT", "name": "Estun Automation(어사돈자동화)", "code": "002747.SZ", "weight": 0.05, "market": "중국 심천"},
    {"rank": 7, "type": "COMPONENT", "name": "Siasun Robot & Automation(신송로봇)", "code": "300024.SZ", "weight": 0.05, "market": "중국 심천"},
    {"rank": 8, "type": "COMPONENT", "name": "Shenzhen Megmeet(맥격미특전기)", "code": "002851.SZ", "weight": 0.045, "market": "중국 심천"},
    {"rank": 9, "type": "COMPONENT", "name": "Efort Intelligent Equipment(애부특지능기인)", "code": "688165.SH", "weight": 0.04, "market": "중국 상해"},
    {"rank": 10, "type": "COMPONENT", "name": "Zhejiang Sanhua Intelligent(삼화)", "code": "002050.SZ", "weight": 0.04, "market": "중국 심천"},
]


def init_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_FILE)
        firebase_admin.initialize_app(cred)
    return firestore.client()


def main():
    db = init_firestore()

    for stock in component_stocks:
        code = stock["code"]

        data = {
            **stock,
            "current": 0,
            "previous": 0,
            "open": 0,
            "high": 0,
            "low": 0,
            "volume": 0,
            "updatedAt": "",
        }

        db.collection("stocks").document(code).set(data, merge=True)
        print(f"저장 완료: {code} / {stock['name']}")

    print("구성종목 10개 Firestore 업로드 완료")


if __name__ == "__main__":
    main()