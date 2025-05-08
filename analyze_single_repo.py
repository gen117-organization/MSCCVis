import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).parent.parent
REPO_JSON_STR = """
 {
        "Java": {
            "ts-food-service": [
                "ts-food-service"
            ],
            "ts-user-service": [
                "ts-user-service"
            ],
            "ts-consign-price-service": [
                "ts-consign-price-service"
            ],
            "ts-travel-service": [
                "ts-travel-service"
            ],
            "ts-admin-travel-service": [
                "ts-admin-travel-service"
            ],
            "ts-consign-service": [
                "ts-consign-service"
            ],
            "ts-preserve-other-service": [
                "ts-preserve-other-service"
            ],
            "ts-assurance-service": [
                "ts-assurance-service"
            ],
            "ts-cancel-service": [
                "ts-cancel-service"
            ],
            "ts-seat-service": [
                "ts-seat-service"
            ],
            "ts-admin-user-service": [
                "ts-admin-user-service"
            ],
            "ts-train-service": [
                "ts-train-service"
            ],
            "ts-execute-service": [
                "ts-execute-service"
            ],
            "ts-route-plan-service": [
                "ts-route-plan-service"
            ],
            "ts-contacts-service": [
                "ts-contacts-service"
            ],
            "ts-price-service": [
                "ts-price-service"
            ],
            "ts-admin-route-service": [
                "ts-admin-route-service"
            ],
            "ts-travel-plan-service": [
                "ts-travel-plan-service"
            ],
            "ts-config-service": [
                "ts-config-service"
            ],
            "ts-travel2-service": [
                "ts-travel2-service"
            ],
            "ts-preserve-service": [
                "ts-preserve-service"
            ],
            "ts-route-service": [
                "ts-route-service"
            ],
            "ts-payment-service": [
                "ts-payment-service"
            ],
            "ts-verification-code-service": [
                "ts-verification-code-service"
            ],
            "ts-notification-service": [
                "ts-notification-service"
            ],
            "ts-rebook-service": [
                "ts-rebook-service"
            ],
            "ts-admin-basic-info-service": [
                "ts-admin-basic-info-service"
            ],
            "ts-order-other-service": [
                "ts-order-other-service"
            ],
            "ts-admin-order-service": [
                "ts-admin-order-service"
            ],
            "ts-basic-service": [
                "ts-basic-service"
            ],
            "ts-security-service": [
                "ts-security-service"
            ],
            "ts-inside-payment-service": [
                "ts-inside-payment-service"
            ],
            "ts-station-service": [
                "ts-station-service"
            ],
            "ts-auth-service": [
                "ts-auth-service"
            ],
            "ts-order-service": [
                "ts-order-service"
            ]
        },
        "JavaScript": {
            "ts-ui-dashboard": [
                "ts-ui-dashboard"
            ],
            "ts-ticket-office-service": [
                "ts-ticket-office-service"
            ]
        },
        "URL": "https://github.com/FudanSELab/train-ticket"
    }
"""

sys.path.append(str(PROJECT_ROOT))
import modules.clone_repo as clone_repo
from modules.detect_cc import analyze_repo


def main():
    repo_json = json.loads(REPO_JSON_STR)
    url = repo_json["URL"]
    name = url.split('/')[-2] + '.' + url.split('/')[-1]
    if not (PROJECT_ROOT / "dest" / "projects" / name).exists():
        clone_repo.clone_repo(url)
    analyze_repo(repo_json)
    

if __name__ == "__main__":
    main()
