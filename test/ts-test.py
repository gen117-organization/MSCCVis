from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import modules.clone_repo
import modules.collect_datas
import modules.analyze_cc
import modules.identify_microservice
import modules.analyze_modification

ts_repo_dict = {
    "languages": {
        "Java": {
            "ts-execute-service": [
                "ts-execute-service"
            ],
            "ts-price-service": [
                "ts-price-service"
            ],
            "ts-travel-service": [
                "ts-travel-service"
            ],
            "ts-verification-code-service": [
                "ts-verification-code-service"
            ],
            "ts-travel2-service": [
                "ts-travel2-service"
            ],
            "ts-consign-service": [
                "ts-consign-service"
            ],
            "ts-user-service": [
                "ts-user-service"
            ],
            "ts-preserve-other-service": [
                "ts-preserve-other-service"
            ],
            "ts-admin-basic-info-service": [
                "ts-admin-basic-info-service"
            ],
            "ts-travel-plan-service": [
                "ts-travel-plan-service"
            ],
            "ts-basic-service": [
                "ts-basic-service"
            ],
            "ts-route-service": [
                "ts-route-service"
            ],
            "ts-admin-route-service": [
                "ts-admin-route-service"
            ],
            "ts-admin-user-service": [
                "ts-admin-user-service"
            ],
            "ts-assurance-service": [
                "ts-assurance-service"
            ],
            "ts-security-service": [
                "ts-security-service"
            ],
            "ts-cancel-service": [
                "ts-cancel-service"
            ],
            "ts-contacts-service": [
                "ts-contacts-service"
            ],
            "ts-admin-travel-service": [
                "ts-admin-travel-service"
            ],
            "ts-order-service": [
                "ts-order-service"
            ],
            "ts-consign-price-service": [
                "ts-consign-price-service"
            ],
            "ts-train-service": [
                "ts-train-service"
            ],
            "ts-admin-order-service": [
                "ts-admin-order-service"
            ],
            "ts-order-other-service": [
                "ts-order-other-service"
            ],
            "ts-food-service": [
                "ts-food-service"
            ],
            "ts-config-service": [
                "ts-config-service"
            ],
            "ts-preserve-service": [
                "ts-preserve-service"
            ],
            "ts-rebook-service": [
                "ts-rebook-service"
            ],
            "ts-notification-service": [
                "ts-notification-service"
            ],
            "ts-route-plan-service": [
                "ts-route-plan-service"
            ],
            "ts-auth-service": [
                "ts-auth-service"
            ],
            "ts-payment-service": [
                "ts-payment-service"
            ],
            "ts-seat-service": [
                "ts-seat-service"
            ],
            "ts-station-service": [
                "ts-station-service"
            ],
            "ts-inside-payment-service": [
                "ts-inside-payment-service"
            ]
        },
        "JavaScript": {
            "ts-ui-dashboard": [
                "ts-ui-dashboard"
            ],
            "ts-ticket-office-service": [
                "ts-ticket-office-service"
            ]
        }
    },
    "URL": "https://github.com/FudanSELab/train-ticket"
}


if __name__ == "__main__":
    url = ts_repo_dict["URL"]
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    workdir = project_root / "dest/projects" / name
    # modules.clone_repo.clone_repo(url)
    # modules.identify_microservice.analyze_repo(url, name, str(workdir))
    # modules.collect_datas.collect_datas_of_repo(ts_repo_dict)
    # modules.analyze_cc.analyze_repo(ts_repo_dict)
    result = modules.analyze_modification.analyze_repo(ts_repo_dict)